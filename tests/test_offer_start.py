import pytest
from brownie import reverts

from purchase_config import DAI_TO_LDO_RATE_PRECISION
from scripts.deploy import deploy_and_start_dao_vote

LDO_ALLOCATIONS = [1_000 * 10**18, 3_000_000 * 10**18, 20_000_000 * 10**18]

# 100 LDO in one DAI
DAI_TO_LDO_RATE = 100 * 10**18

VESTING_START_DELAY = 1 * 60 * 60 * 24 * 365 # one year
VESTING_END_DELAY = 2 * 60 * 60 * 24 * 365 # two years
OFFER_EXPIRATION_DELAY = 2629746 # one month

DIRECT_TRANSFER_GAS_LIMIT=300_000


@pytest.fixture(scope='function')
def deployed_executor_and_vote_id(accounts, ldo_holder):
    return deploy_and_start_dao_vote(
        {'from': ldo_holder},
        dai_to_ldo_rate=DAI_TO_LDO_RATE,
        vesting_start_delay=VESTING_START_DELAY,
        vesting_end_delay=VESTING_END_DELAY,
        offer_expiration_delay=OFFER_EXPIRATION_DELAY,
        ldo_purchasers=[ (accounts[i], LDO_ALLOCATIONS[i]) for i in range(0, len(LDO_ALLOCATIONS)) ],
        allocations_total=sum(LDO_ALLOCATIONS)
    )

@pytest.fixture(scope='function')
def deployed_executor(deployed_executor_and_vote_id):
    return deployed_executor_and_vote_id[0]

@pytest.fixture(scope='function')
def funding_vote_id(deployed_executor_and_vote_id):
    return deployed_executor_and_vote_id[1]


def test_offer_not_started_after_deploy(deployed_executor):
    assert not deployed_executor.offer_started()


def test_offer_not_expired_after_deploy(deployed_executor):
    assert not deployed_executor.offer_expired()


def test_offer_cannot_be_started_until_executor_funded(stranger, ldo_holder, deployed_executor):
    with reverts('not funded'):
        deployed_executor.start({ 'from': stranger })

    with reverts('not funded'):
        deployed_executor.start({ 'from': ldo_holder })


def test_purchase_cannot_be_executed_before_offer_start(accounts, deployed_executor):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]
    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    with reverts('not allowed'):
        purchaser.transfer(to=deployed_executor, amount=dai_cost, gas_limit=400_000)

    with reverts('not funded'):
        deployed_executor.execute_purchase(purchaser, { 'from': purchaser })


def test_offer_can_be_started_by_anyone_after_funding(
    stranger,
    deployed_executor,
    funding_vote_id,
    helpers
):
    helpers.pass_and_exec_dao_vote(funding_vote_id)

    assert not deployed_executor.offer_started()
    assert not deployed_executor.offer_expired()

    tx = deployed_executor.start({ 'from': stranger })

    assert deployed_executor.offer_started()
    assert deployed_executor.offer_started_at() == tx.timestamp
    assert deployed_executor.offer_expires_at() == tx.timestamp + OFFER_EXPIRATION_DELAY
    assert not deployed_executor.offer_expired()

    start_evt = helpers.assert_single_event_named('OfferStarted', tx)

    assert start_evt['started_at'] == tx.timestamp
    assert start_evt['expires_at'] == tx.timestamp + OFFER_EXPIRATION_DELAY


def test_offer_automatically_starts_after_funding_on_first_deposit(
    accounts,
    deployed_executor,
    funding_vote_id,
    ldo_token,
    helpers,
    dai_token
):
    helpers.pass_and_exec_dao_vote(funding_vote_id)

    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]
    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE

    #add dai to purchaser
    helpers.fund_with_dai(purchaser, dai_cost)
    dai_token.approve(deployed_executor, dai_cost, { 'from': purchaser })

    tx = deployed_executor.execute_purchase(purchaser, { 'from': purchaser })

    start_evt = helpers.assert_single_event_named('OfferStarted', tx)
    purchase_evt = helpers.assert_single_event_named('PurchaseExecuted', tx)

    assert deployed_executor.offer_started()
    assert start_evt['started_at'] == tx.timestamp
    assert start_evt['expires_at'] == tx.timestamp + OFFER_EXPIRATION_DELAY
    assert not deployed_executor.offer_expired()

    assert ldo_token.balanceOf(purchaser) == purchase_ldo_amount
    assert purchase_evt['ldo_receiver'] == purchaser
    assert purchase_evt['ldo_allocation'] == purchase_ldo_amount
    assert purchase_evt['dai_cost'] == dai_cost


def test_erc20_cannot_be_recovered_before_offer_start(
    ldo_holder,
    ldo_token,
    deployed_executor,
    funding_vote_id,
    helpers
):
    helpers.pass_and_exec_dao_vote(funding_vote_id)
    with reverts("dev: offer not expired"):
        deployed_executor.recover_erc20(ldo_token.address, 1)
