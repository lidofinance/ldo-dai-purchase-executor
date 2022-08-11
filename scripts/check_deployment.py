import os
import brownie
from brownie import chain, accounts, interface, PurchaseExecutor

from utils.mainnet_fork import chain_snapshot, pass_and_exec_dao_vote
from utils.config import ldo_token_address, lido_dao_agent_address, get_is_live, dai_token_address

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
    print(f'Using deployed executor at address {executor_address}')

    executor = PurchaseExecutor.at(executor_address)

    check_config(executor)
    check_allocations(executor)

    print(f'[ok] Executor is configured correctly')

    if get_is_live():
        print('Running on a live network, cannot check allocations reception.')
        print('Run on a mainnet fork to do this.')
        return

    with chain_snapshot():
        if 'VOTE_IDS' in os.environ:
            for vote_id in os.environ['VOTE_IDS'].split(','):
                pass_and_exec_dao_vote(int(vote_id))

        check_allocations_reception(executor)

    print(f'All good!')


def check_config(executor):
    print(f'DAILDO rate: {DAI_TO_LDO_RATE / 10**18}')
    assert executor.dai_to_ldo_rate() == DAI_TO_LDO_RATE

    print(f'Offer expiration delay: {OFFER_EXPIRATION_DELAY / SECONDS_IN_A_DAY} days')
    assert executor.offer_expiration_delay() == OFFER_EXPIRATION_DELAY

    print(f'Vesting start delay: {VESTING_START_DELAY / SECONDS_IN_A_DAY} days')
    assert executor.vesting_start_delay() == VESTING_START_DELAY

    print(f'Vesting end delay: {VESTING_END_DELAY / SECONDS_IN_A_DAY} days')
    assert executor.vesting_end_delay() == VESTING_END_DELAY

    print(f'[ok] Global config is correct')


def check_allocations(executor):
    print(f'Total allocation: {TOTAL_LDO_SOLD / 10**18} LDO')
    assert executor.ldo_allocations_total() == TOTAL_LDO_SOLD

    for (purchaser, expected_allocation) in LDO_PURCHASERS:
        (allocation, dai_cost) = executor.get_allocation(purchaser)
        print(f'  {purchaser}: {allocation / 10**18} LDO, {dai_cost} wei')
        expected_cost = expected_allocation * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE
        assert allocation == expected_allocation
        assert dai_cost == expected_cost

    print(f'[ok] Allocations are correct')


def check_allocations_reception(executor):
    dai_banker = accounts.at('0x075e72a5edf65f0a5f44699c7654c1a76941ddc8', force=True)

    dai_token = interface.ERC20(dai_token_address)
    ldo_token = interface.ERC20(ldo_token_address)
    lido_dao_agent = interface.Agent(lido_dao_agent_address)
    executor_ldo_balance = ldo_token.balanceOf(executor.address)

    print(f'Executor LDO balance: {TOTAL_LDO_SOLD / 10**18} LDO')
    assert executor_ldo_balance == TOTAL_LDO_SOLD
    print('[ok] Executor fully funded')

    if not executor.offer_started():
        print(f'Starting the offer')
        executor.start({'from': accounts[0]})
        assert executor.offer_started()

    print('[ok] Offer started')


    print(f'Offer lasts {OFFER_EXPIRATION_DELAY / SECONDS_IN_A_DAY} days')
    assert executor.offer_expires_at() == executor.offer_started_at() + OFFER_EXPIRATION_DELAY

    print(f'Checking allocations reception')

    dao_agent_dai_balance_before = dai_token.balanceOf(lido_dao_agent)

    for i, (purchaser, expected_allocation) in enumerate(LDO_PURCHASERS):
        (allocation, dai_cost) = executor.get_allocation(purchaser)

        print(f'  {purchaser}: {expected_allocation / 10**18} LDO, {dai_cost} wei')

        assert allocation == expected_allocation

        purchaser_acct = accounts.at(purchaser, force=True)
        purchaser_dai_balance_before = dai_token.balanceOf(purchaser)

        overpay = 10**17 * (i % 2)

        if purchaser_dai_balance_before < dai_cost + overpay:
            print(f'    funding the purchaser account with DAI...')
            dai_token.transfer(purchaser, dai_cost + overpay - purchaser_dai_balance_before, { 'from': dai_banker })
            purchaser_dai_balance_before = dai_cost + overpay

        purchaser_ldo_balance_before = ldo_token.balanceOf(purchaser)

        print(f'    the purchase approve DAI: {dai_cost / 10**18} DAI...')
        dai_token.approve(executor, dai_cost, { 'from': purchaser })

        print(f'    executing the purchase: {dai_cost / 10**18} DAI...')
        tx = executor.execute_purchase(purchaser, { 'from': purchaser })

        ldo_purchased = ldo_token.balanceOf(purchaser) - purchaser_ldo_balance_before
        dai_spent = purchaser_dai_balance_before - dai_token.balanceOf(purchaser)

        assert ldo_purchased == allocation
        assert dai_spent == dai_cost
        print(f'    [ok] the purchase executed correctly, gas used: {tx.gas_used}')

    expected_total_dai_cost = TOTAL_LDO_SOLD * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE
    total_dai_received = dai_token.balanceOf(lido_dao_agent) - dao_agent_dai_balance_before

    print(f'Total DAI received by the DAO, expected: {expected_total_dai_cost}')
    print(f'Total DAI received by the DAO: {total_dai_received}')

    assert total_dai_received == expected_total_dai_cost
    print(f'[ok] Total DAI received is correct')

    print(f'[ok] No LDO left on executor')
    assert ldo_token.balanceOf(executor.address) == 0

    print(f'[ok] No DAI left on executor')
    assert dai_token.balanceOf(executor) == 0
