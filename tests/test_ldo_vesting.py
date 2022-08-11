import pytest
from brownie import chain, reverts

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
        total_ldo_sold=sum(LDO_ALLOCATIONS)
    )
    executor.start({ 'from': accounts[0] })
    return executor


@pytest.fixture(scope='function')
def purchaser(helpers, accounts, executor, ldo_token, dai_token):
    purchaser = accounts[0]
    purchase_ldo_amount = LDO_ALLOCATIONS[0]

    dai_cost = purchase_ldo_amount * DAI_TO_LDO_RATE_PRECISION // DAI_TO_LDO_RATE
    
    #add dai to purchaser
    helpers.fund_with_dai(purchaser, dai_cost)

    dai_token.approve(executor, dai_cost, { 'from': purchaser })

    executor.execute_purchase(purchaser, { 'from': purchaser })

    assert ldo_token.balanceOf(purchaser) > 0

    return purchaser


def test_transfer_not_allowed_before_vesting_start(executor, purchaser, stranger, ldo_token):
    with reverts():
        ldo_token.transfer(stranger, 1, {'from': purchaser})

    chain.sleep(VESTING_START_DELAY // 2)

    with reverts():
        ldo_token.transfer(stranger, 1, {'from': purchaser})

    chain.sleep(VESTING_START_DELAY // 2 - 10)

    with reverts():
        ldo_token.transfer(stranger, 1, {'from': purchaser})


def test_tokens_will_begin_becoming_transferable_linearly(purchaser, stranger, ldo_token):
    chain.sleep(VESTING_START_DELAY + 60)
    ldo_token.transfer(stranger, 1, {'from': purchaser})

    vesting_duration = VESTING_END_DELAY - VESTING_START_DELAY
    chain.sleep(vesting_duration // 3)

    stranger_balance = ldo_token.balanceOf(stranger)
    purchaser_balance = ldo_token.balanceOf(purchaser)

    with reverts():
        ldo_token.transfer(stranger, purchaser_balance, {'from': purchaser})

    with reverts():
        ldo_token.transfer(stranger, purchaser_balance // 2, {'from': purchaser})

    ldo_token.transfer(stranger, purchaser_balance // 3 - 1, {'from': purchaser})

    assert ldo_token.balanceOf(purchaser) == purchaser_balance - purchaser_balance // 3 + 1
    assert ldo_token.balanceOf(stranger) == stranger_balance + purchaser_balance // 3 - 1

    chain.sleep(vesting_duration // 3)

    with reverts():
        ldo_token.transfer(stranger, ldo_token.balanceOf(purchaser), {'from': purchaser})

    ldo_token.transfer(stranger, purchaser_balance // 3 - 1, {'from': purchaser})

    assert ldo_token.balanceOf(purchaser) == purchaser_balance - 2 * purchaser_balance // 3 + 2
    assert ldo_token.balanceOf(stranger) == stranger_balance + 2 * purchaser_balance // 3 - 2


def test_vesting_will_end_after_vesting_end_delay(purchaser, stranger, ldo_token):
    stranger_balance = ldo_token.balanceOf(stranger)
    purchaser_balance = ldo_token.balanceOf(purchaser)

    chain.sleep(VESTING_END_DELAY + 1)
    ldo_token.transfer(stranger, purchaser_balance, {'from': purchaser})

    assert ldo_token.balanceOf(purchaser) == 0
    assert ldo_token.balanceOf(stranger) == stranger_balance + purchaser_balance

