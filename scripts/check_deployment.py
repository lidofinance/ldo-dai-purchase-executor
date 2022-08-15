import os
import brownie
from brownie import chain, accounts, interface, PurchaseExecutor

from utils.mainnet_fork import chain_snapshot, pass_and_exec_dao_vote
from utils.log import ok, warn, nb, h, assert_equals, highlight as hl
from utils.config import (
    ldo_token_address,
    lido_dao_agent_address,
    lido_dao_acl_address,
    lido_dao_token_manager_address,
    get_is_live,
    dai_token_address
)

from purchase_config import (
    SECONDS_IN_A_DAY,
    DAI_TO_LDO_RATE_PRECISION,
    DAI_TO_LDO_RATE,
    VESTING_START_DELAY,
    VESTING_END_DELAY,
    OFFER_EXPIRATION_DELAY,
    LDO_PURCHASERS,
    TOTAL_LDO_SOLD
)

def main():
    if 'EXECUTOR_ADDRESS' not in os.environ:
        raise EnvironmentError('Please set the EXECUTOR_ADDRESS environment variable')

    executor_address = os.environ['EXECUTOR_ADDRESS']
    nb('Using deployed executor at address', executor_address)

    executor = PurchaseExecutor.at(executor_address)

    print()
    check_config(executor)
    print()
    check_permissions(executor)
    print()
    check_allocations(executor)
    print()
    check_funding(executor)
    print()

    ok(f'Executor is configured correctly')

    if get_is_live():
        nb('Running on a live network, cannot check allocations reception.')
        nb('Run on a mainnet fork to do this.')
        return

    with chain_snapshot():
        if 'VOTE_IDS' in os.environ:
            h('Executing votes...')
            for vote_id in os.environ['VOTE_IDS'].split(','):
                pass_and_exec_dao_vote(int(vote_id))
            print()

        purchase_timestamps = check_allocations_reception(executor)
        print()
        check_lockup(purchase_timestamps)

    h(f'All good!')


def check_config(executor):
    print(f'DAILDO rate: {hl(DAI_TO_LDO_RATE / 10**18)}')
    assert executor.dai_to_ldo_rate() == DAI_TO_LDO_RATE

    print(f'LDODAI rate: {hl(10**18 / DAI_TO_LDO_RATE)}')

    print(f'Offer expiration delay: {hl(OFFER_EXPIRATION_DELAY / SECONDS_IN_A_DAY)} days')
    assert executor.offer_expiration_delay() == OFFER_EXPIRATION_DELAY

    print(f'Vesting start delay: {hl(VESTING_START_DELAY / SECONDS_IN_A_DAY)} days')
    assert executor.vesting_start_delay() == VESTING_START_DELAY

    print(f'Vesting end delay: {hl(VESTING_END_DELAY / SECONDS_IN_A_DAY)} days')
    assert executor.vesting_end_delay() == VESTING_END_DELAY

    print()
    ok(f'Global config is correct')


def check_permissions(executor):
    acl = interface.ACL(lido_dao_acl_address)
    token_manager = interface.TokenManager(lido_dao_token_manager_address)
    if acl.hasPermission(executor, token_manager, token_manager.ASSIGN_ROLE()):
        ok('Executor has permission to assign tokens')
    else:
        warn('Executor has no permission to assign tokens')


def check_funding(executor):
    ldo_token = interface.ERC20(ldo_token_address)
    total_ldo_sold = executor.ldo_allocations_total()
    exec_ldo_balance = ldo_token.balanceOf(executor)
    if exec_ldo_balance == total_ldo_sold:
        ok(f'Executor is funded, balance: {hl(exec_ldo_balance / 10**18)} LDO')
    elif exec_ldo_balance > total_ldo_sold:
        excess_funding = exec_ldo_balance - total_ldo_sold
        ok(f'Executor is over-funded by {hl(excess_funding / 10**18)} LDO, balance: {hl(exec_ldo_balance / 10**18)} LDO')
    else:
        warn(f'Executor is under-funded, balance: {hl(exec_ldo_balance / 10**18)} LDO')


def check_allocations(executor):
    print(f'Total allocation: {hl(TOTAL_LDO_SOLD / 10**18)} LDO')
    assert executor.ldo_allocations_total() == TOTAL_LDO_SOLD

    for (purchaser, expected_allocation) in LDO_PURCHASERS:
        (allocation, dai_cost) = executor.get_allocation(purchaser)
        print(f'  {purchaser}: {hl(allocation / 10**18)} LDO, {hl(dai_cost / 10**18)} DAI')
        expected_cost = expected_allocation * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE
        assert allocation == expected_allocation
        assert dai_cost == expected_cost

    print()
    ok(f'Allocations are correct')


def check_allocations_reception(executor):
    dai_banker = accounts.at('0x075e72a5edf65f0a5f44699c7654c1a76941ddc8', force=True)

    dai_token = interface.ERC20(dai_token_address)
    ldo_token = interface.ERC20(ldo_token_address)
    lido_dao_agent = interface.Agent(lido_dao_agent_address)
    executor_ldo_balance = ldo_token.balanceOf(executor.address)

    assert executor_ldo_balance == TOTAL_LDO_SOLD
    ok(f'Executor LDO balance: {hl(TOTAL_LDO_SOLD / 10**18)} LDO')

    if not executor.offer_started():
        print()
        nb(f'Starting the offer')
        executor.start({'from': accounts[0]})
        assert executor.offer_started()

    ok('Offer started')

    assert executor.offer_expires_at() == executor.offer_started_at() + OFFER_EXPIRATION_DELAY
    ok(f'Offer lasts {hl(OFFER_EXPIRATION_DELAY / SECONDS_IN_A_DAY)} days')

    h(f'Checking allocations reception')

    ldo_black_hole = accounts.add()
    purchase_timestamps = []

    dao_agent_dai_balance_before = dai_token.balanceOf(lido_dao_agent)

    for i, (purchaser, expected_allocation) in enumerate(LDO_PURCHASERS):
        (allocation, dai_cost) = executor.get_allocation(purchaser)

        print()
        nb(f'Purchaser: {hl(purchaser)}')
        nb(f'Total {hl(expected_allocation / 10**18)} LDO for {hl(dai_cost / 10**18)} DAI')

        assert allocation == expected_allocation

        purchaser_acct = accounts.at(purchaser, force=True)

        purchaser_ldo_balance_before = ldo_token.balanceOf(purchaser)
        if purchaser_ldo_balance_before > 0:
            print('\nTransferring out pre-owned LDO')
            ldo_token.transfer(ldo_black_hole, purchaser_ldo_balance_before, { 'from': purchaser })

        purchaser_dai_balance_before = dai_token.balanceOf(purchaser)

        overpay = 10**17 * (i % 2)

        if purchaser_dai_balance_before < dai_cost + overpay:
            print(f'\nFunding the purchaser account with DAI')
            dai_token.transfer(purchaser, dai_cost + overpay - purchaser_dai_balance_before, { 'from': dai_banker })
            purchaser_dai_balance_before = dai_cost + overpay

        purchaser_ldo_balance_before = ldo_token.balanceOf(purchaser)

        print(f'Approving DAI for purchase: {hl(dai_cost)}')
        tx = dai_token.approve(executor, dai_cost, { 'from': purchaser })
        print(f'Tx data: {tx.input}\n')

        print(f'Executing the purchase...')
        tx = executor.execute_purchase({ 'from': purchaser })
        purchase_timestamps = purchase_timestamps + [tx.timestamp]
        print(f'Tx data: {tx.input}\n')

        ldo_purchased = ldo_token.balanceOf(purchaser) - purchaser_ldo_balance_before
        dai_spent = purchaser_dai_balance_before - dai_token.balanceOf(purchaser)

        assert ldo_purchased == allocation
        assert dai_spent == dai_cost
        ok(f'The purchase executed correctly, gas used: {hl(tx.gas_used)}')

    print()
    ok('All purchases executed correctly')
    print()

    expected_total_dai_cost = TOTAL_LDO_SOLD * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE
    total_dai_received = dai_token.balanceOf(lido_dao_agent) - dao_agent_dai_balance_before

    assert_equals('Total DAI received by the DAO', total_dai_received, expected_total_dai_cost)

    assert ldo_token.balanceOf(executor.address) == 0
    ok(f'No LDO left on executor')

    assert dai_token.balanceOf(executor) == 0
    ok(f'No DAI left on executor')

    return purchase_timestamps


def check_lockup(purchase_timestamps):
    h('Checking lockup')

    assert VESTING_START_DELAY > 0
    assert VESTING_END_DELAY == VESTING_START_DELAY

    ldo_token = interface.ERC20(ldo_token_address)
    ldo_recipient = accounts.add()

    def assert_ldo_is_not_transferrable(purchaser_acct, allocation, i):
        try:
            tx = ldo_token.transfer(ldo_recipient, 1, { 'from': purchaser_acct })
            tx.info()
            raise AssertionError(f'transfer of 1 wei LDO succeeded from {purchaser_acct}')
        except brownie.exceptions.VirtualMachineError as err:
            print(f'[ok] transfer reverted: {err}')

    def assert_ldo_is_fully_transferrable(purchaser_acct, allocation, i):
        assert ldo_token.balanceOf(purchaser_acct) > 0
        ldo_token.transfer(ldo_recipient, allocation, { 'from': purchaser_acct })
        assert ldo_token.balanceOf(purchaser_acct) == 0

    def run_for_each_purchaser_at_delay(delay_from_purchase, fn):
        for i, (purchaser, allocation) in enumerate(LDO_PURCHASERS):
            purchaser_acct = accounts.at(purchaser, force=True)
            purchase_timestamp = purchase_timestamps[i]
            print(f'\nholder {hl(purchaser)} at delay {hl(delay_from_purchase)}')
            with chain_snapshot():
                if delay_from_purchase > 0:
                    final_time = purchase_timestamp + delay_from_purchase
                    chain.sleep(final_time - chain.time())
                fn(purchaser_acct, allocation, i)
            ok('check passed')

    print()
    nb(f'Checking that lock-up is effective immediately')
    run_for_each_purchaser_at_delay(0, assert_ldo_is_not_transferrable)

    print()
    nb(f'Checking that lock-up is effective for the full time period')
    run_for_each_purchaser_at_delay(VESTING_START_DELAY - 1, assert_ldo_is_not_transferrable)

    print()
    nb(f'Checking that lock-up is lifted after the lock-up period passes')
    run_for_each_purchaser_at_delay(VESTING_START_DELAY + 1, assert_ldo_is_fully_transferrable)
