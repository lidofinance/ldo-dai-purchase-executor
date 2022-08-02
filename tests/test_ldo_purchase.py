import pytest
from brownie import reverts
from brownie.network.state import Chain

from purchase_config import DAI_TO_LDO_RATE_PRECISION

LDO_ALLOCATIONS = [
    1_000 * 10**18,
    3_000_000 * 10**18,
    20_000_000 * 10**18
]

# 100 LDO in one DAI
DAI_TO_LDO_RATE = 100 * 10**18

VESTING_START_DELAY = 1 * 60 * 60 * 24 * 365 # one year
VESTING_END_DELAY = 2 * 60 * 60 * 24 * 365 # two years
OFFER_EXPIRATION_DELAY = 2629746 # one month

@pytest.fixture(scope='function')
def executor(accounts, deploy_executor_and_pass_dao_vote):
    executor = deploy_executor_and_pass_dao_vote(
        dai_to_ldo_rate=DAI_TO_LDO_RATE,
        vesting_start_delay=VESTING_START_DELAY,
        vesting_end_delay=VESTING_END_DELAY,
        offer_expiration_delay=OFFER_EXPIRATION_DELAY,
        ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
        allocations_total=sum(LDO_ALLOCATIONS)
    )
    executor.start({ 'from': accounts[0] })
    return executor


def test_deploy_fails_on_wrong_allocations_total(accounts, deploy_executor_and_pass_dao_vote):
    with reverts():
        deploy_executor_and_pass_dao_vote(
            dai_to_ldo_rate=DAI_TO_LDO_RATE,
            vesting_start_delay=VESTING_START_DELAY,
            vesting_end_delay=VESTING_END_DELAY,
            offer_expiration_delay=OFFER_EXPIRATION_DELAY,
            ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
            allocations_total=sum(LDO_ALLOCATIONS) + 1
        )


def test_deploy_fails_on_zero_rate(accounts, deploy_executor_and_pass_dao_vote):
    with reverts():
        deploy_executor_and_pass_dao_vote(
            dai_to_ldo_rate=0,
            vesting_start_delay=VESTING_START_DELAY,
            vesting_end_delay=VESTING_END_DELAY,
            offer_expiration_delay=OFFER_EXPIRATION_DELAY,
            ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
            allocations_total=sum(LDO_ALLOCATIONS)
        )


def test_deploy_fails_on_vesting_ends_before_start(accounts, deploy_executor_and_pass_dao_vote):
    with reverts():
        deploy_executor_and_pass_dao_vote(
            dai_to_ldo_rate=DAI_TO_LDO_RATE,
            vesting_start_delay=VESTING_START_DELAY,
            vesting_end_delay=VESTING_START_DELAY - 1,
            offer_expiration_delay=OFFER_EXPIRATION_DELAY,
            ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
            allocations_total=sum(LDO_ALLOCATIONS)
        )


def test_deploy_fails_on_zero_offer_exparation_delay(accounts, deploy_executor_and_pass_dao_vote):
    with reverts():
        deploy_executor_and_pass_dao_vote(
            dai_to_ldo_rate=DAI_TO_LDO_RATE,
            vesting_start_delay=VESTING_START_DELAY,
            vesting_end_delay=VESTING_END_DELAY,
            offer_expiration_delay=0,
            ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
            allocations_total=sum(LDO_ALLOCATIONS)
        )


def test_deploy_fails_on_purchasers_duplicates(accounts, deploy_executor_and_pass_dao_vote):
    with reverts():
        deploy_executor_and_pass_dao_vote(
            dai_to_ldo_rate=DAI_TO_LDO_RATE,
            vesting_start_delay=VESTING_START_DELAY,
            vesting_end_delay=VESTING_END_DELAY,
            offer_expiration_delay=OFFER_EXPIRATION_DELAY,
            ldo_purchasers=[ (accounts[0], LDO_ALLOCATIONS[0]) for i in range(0, len(LDO_ALLOCATIONS)) ],
            allocations_total=sum(LDO_ALLOCATIONS)
        )


def test_executor_config_is_correct(executor):
    assert executor.dai_to_ldo_rate() == DAI_TO_LDO_RATE
    assert executor.vesting_start_delay() == VESTING_START_DELAY
    assert executor.vesting_end_delay() == VESTING_END_DELAY
    assert executor.offer_expiration_delay() == OFFER_EXPIRATION_DELAY
    assert executor.ldo_allocations_total() == sum(LDO_ALLOCATIONS)
    assert executor.offer_started()
    assert executor.offer_expires_at() == executor.offer_started_at() + OFFER_EXPIRATION_DELAY


def test_ether_transfers_not_accepted(accounts, executor, dao_agent, helpers, ldo_token, dao_token_manager):
    purchaser = accounts[0]

    with reverts("not allowed"):
        purchaser.transfer(to=executor, amount=1, gas_limit=1_000_000)

    with reverts("not allowed"):
        purchaser.transfer(to=executor, amount=10**18, gas_limit=1_000_000)

    allocation = executor.get_allocation(purchaser)
    dai_cost = allocation[1]
    helpers.fund_with_dai(purchaser, dai_cost)

    with reverts("not allowed"):
        purchaser.transfer(to=executor, amount=dai_cost, gas_limit=1_000_000)


def test_purchase(accounts, executor, dao_agent, helpers, ldo_token, dao_token_manager, dai_token):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(purchaser)
    assert allocation[0] == purchase_ldo_amount
    assert allocation[1] == dai_cost

    extra_allowance = 10**18

    #add dai to purchaser
    helpers.fund_with_dai(purchaser, dai_cost + extra_allowance)

    dai_purchaser_balance_before = dai_token.balanceOf(purchaser)
    dai_agent_balance_before = dai_token.balanceOf(dao_agent)

    dai_token.approve(executor, dai_cost + extra_allowance, { 'from': purchaser })

    #execute purchase
    tx = executor.execute_purchase(purchaser, { 'from': purchaser })
    purchase_evt = helpers.assert_single_event_named('PurchaseExecuted', tx)

    assert purchase_evt['ldo_receiver'] == purchaser
    assert purchase_evt['ldo_allocation'] == purchase_ldo_amount
    assert purchase_evt['dai_cost'] == dai_cost

    #agent DAI increase
    dai_agent_balance_after = dai_token.balanceOf(dao_agent)
    dao_dai_balance_increase = dai_agent_balance_after - dai_agent_balance_before
    assert dao_dai_balance_increase == dai_cost
    assert ldo_token.balanceOf(purchaser) == purchase_ldo_amount

    #purchaser DAI decrease
    dai_purchaser_balance_after = dai_token.balanceOf(purchaser)
    dai_purchaser_balance_decrease = dai_purchaser_balance_before - dai_purchaser_balance_after
    assert dai_purchaser_balance_decrease == dai_cost

    vesting = dao_token_manager.getVesting(purchaser, purchase_evt['vesting_id'])

    assert vesting['amount'] == purchase_ldo_amount
    assert vesting['start'] == tx.timestamp + VESTING_START_DELAY
    assert vesting['cliff'] == tx.timestamp + VESTING_START_DELAY
    assert vesting['vesting'] == tx.timestamp + VESTING_END_DELAY
    assert vesting['revokable'] == False


def test_stranger_not_allowed_to_purchase(accounts, executor, helpers):
    purchase_ldo_amount = LDO_ALLOCATIONS[0]
    stranger = accounts[5]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(stranger)
    assert allocation[0] == 0
    assert allocation[1] == 0

    helpers.fund_with_dai(stranger, dai_cost)

    with reverts("no allocation"):
        executor.execute_purchase(stranger, { 'from': stranger })


def test_stranger_allowed_to_purchase_token_for_purchaser(accounts, executor, dao_agent, helpers, ldo_token, dao_token_manager, dai_token):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]
    stranger = accounts[5]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(purchaser)
    assert allocation[0] == purchase_ldo_amount
    assert allocation[1] == dai_cost

    helpers.fund_with_dai(stranger, dai_cost)

    dai_stranger_balance_before = dai_token.balanceOf(stranger)
    dai_agent_balance_before = dai_token.balanceOf(dao_agent)

    dai_token.approve(executor, dai_cost, { 'from': stranger })

    tx = executor.execute_purchase(purchaser, { 'from': stranger })
    purchase_evt = helpers.assert_single_event_named('PurchaseExecuted', tx)

    assert purchase_evt['ldo_receiver'] == purchaser
    assert purchase_evt['ldo_allocation'] == purchase_ldo_amount
    assert purchase_evt['dai_cost'] == dai_cost

    #agent DAI increase
    dai_agent_balance_after = dai_token.balanceOf(dao_agent)
    dao_dai_balance_increase = dai_agent_balance_after - dai_agent_balance_before
    assert dao_dai_balance_increase == dai_cost
    assert ldo_token.balanceOf(purchaser) == purchase_ldo_amount

    #purchaser DAI decrease
    dai_stranger_balance_after = dai_token.balanceOf(stranger)
    dai_stranger_balance_decrease = dai_stranger_balance_before - dai_stranger_balance_after
    assert dai_stranger_balance_decrease == dai_cost

    vesting = dao_token_manager.getVesting(purchaser, purchase_evt['vesting_id'])

    assert vesting['amount'] == purchase_ldo_amount
    assert vesting['start'] == tx.timestamp + VESTING_START_DELAY
    assert vesting['cliff'] == tx.timestamp + VESTING_START_DELAY
    assert vesting['vesting'] == tx.timestamp + VESTING_END_DELAY
    assert vesting['revokable'] == False


def test_purchase_fails_with_insufficient_allowance(accounts, executor, helpers):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(purchaser)
    assert allocation[0] == purchase_ldo_amount
    assert allocation[1] == dai_cost

    dai_cost = dai_cost - 1e18

    helpers.fund_with_dai(purchaser, dai_cost)

    with reverts():
        executor.execute_purchase(purchaser, { 'from': purchaser })


def test_double_purchase_not_allowed(accounts, executor, dao_agent, helpers, dai_token):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(purchaser)
    assert allocation[0] == purchase_ldo_amount
    assert allocation[1] == dai_cost

    helpers.fund_with_dai(purchaser, 2 * dai_cost)

    dai_token.approve(executor, dai_cost, { 'from': purchaser })
    executor.execute_purchase(purchaser, { 'from': purchaser })

    dai_token.approve(executor, dai_cost, { 'from': purchaser })

    with reverts("no allocation"):
        executor.execute_purchase(purchaser, { 'from': purchaser })


def test_purchase_not_allowed_after_expiration(accounts, executor, helpers):
    chain = Chain()

    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    allocation = executor.get_allocation(purchaser)
    assert allocation[0] == purchase_ldo_amount
    assert allocation[1] == dai_cost

    helpers.fund_with_dai(purchaser, dai_cost)

    expiration_delay = executor.offer_expires_at() - chain.time()
    chain.sleep(expiration_delay + 3600)
    chain.mine()

    with reverts("offer expired"):
        executor.execute_purchase(purchaser, { 'from': purchaser  })


def test_recover_erc20_reverts_before_offer_exparation(stranger, executor, dao_agent, ldo_token, dai_token, helpers):
    helpers.fund_with_dai(stranger, 10**18)
    dai_token.transfer(executor, 10**18, { 'from': stranger })

    with reverts("dev: offer not expired"):
        executor.recover_erc20(ldo_token.address, 1, { 'from': stranger })

    with reverts("dev: offer not expired"):
        executor.recover_erc20(dai_token.address, 10**18, { 'from': stranger })


def test_recover_erc20_can_return_dai_tokens_to_dao_vault_after_exparation(ldo_holder, stranger, executor, dao_agent, dai_token, helpers):
    helpers.fund_with_dai(ldo_holder, 10**18)
    dai_token.transfer(executor, 10**18, { 'from': ldo_holder })

    chain = Chain()
    expiration_delay = executor.offer_expires_at() - chain.time()
    chain.sleep(expiration_delay + 3600)
    chain.mine()

    executor_dai_balance = dai_token.balanceOf(executor)
    dao_agent_dai_balance = dai_token.balanceOf(dao_agent)

    assert executor_dai_balance == 10**18

    executor.recover_erc20(dai_token.address, 10**18, { 'from': stranger })

    assert dai_token.balanceOf(executor) == 0
    assert dai_token.balanceOf(dao_agent) == executor_dai_balance + dao_agent_dai_balance


def test_recover_erc20_can_return_all_ldo_tokens_to_dao_vault_after_exparation(executor, dao_agent, ldo_token, stranger):
    chain = Chain()

    expiration_delay = executor.offer_expires_at() - chain.time()
    chain.sleep(expiration_delay + 3600)
    chain.mine()

    executor_ldo_balance = ldo_token.balanceOf(executor)
    dao_agent_ldo_balance = ldo_token.balanceOf(dao_agent)

    assert executor_ldo_balance != 0

    executor.recover_erc20(ldo_token, executor_ldo_balance, { 'from': stranger })

    assert ldo_token.balanceOf(executor) == 0
    assert ldo_token.balanceOf(dao_agent) == dao_agent_ldo_balance + executor_ldo_balance


def test_recover_erc20_can_return_unsold_ldo_tokens_to_dao_vault_after_exparation(helpers, accounts, executor, dao_agent, ldo_token, dai_token, stranger):
    chain = Chain()

    purchaser = accounts[0]
    allocation = executor.get_allocation(purchaser)
    purchase_ldo_amount = allocation[0]
    dai_cost = allocation[1]

    helpers.fund_with_dai(purchaser, dai_cost)
    dai_token.approve(executor, dai_cost, { 'from': purchaser })
    executor.execute_purchase(purchaser, { 'from': purchaser })

    executor_ldo_balance = ldo_token.balanceOf(executor)
    dao_agent_ldo_balance = ldo_token.balanceOf(dao_agent)

    assert executor_ldo_balance != 0

    expiration_delay = executor.offer_expires_at() - chain.time()
    chain.sleep(expiration_delay + 3600)
    chain.mine()

    executor.recover_erc20(ldo_token, executor_ldo_balance, { 'from': stranger })

    assert ldo_token.balanceOf(executor) == 0
    assert ldo_token.balanceOf(dao_agent) == dao_agent_ldo_balance + executor_ldo_balance
