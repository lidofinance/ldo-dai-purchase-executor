# LDO purchase executor

Allows a predefined list of addresses to purchase vested LDO tokens
from the DAO treasury in exchange for DAI at the predefined rate.
Implements the second approach (one-by-one) from
[the proposal](https://hackmd.io/@skozin/BkJR_UdSd):

Each participants can execute their part of the deal individually with individually assigned lock/vesting times based on time of the purchase. The opprtunity to participate expires in one month.

The [`PurchaseExecutor`](./contracts/PurchaseExecutor.vy) smart contract provides the following interface:

* `__init__(dai_to_ldo_rate: uint256, vesting_start_delay: uint256, vesting_end_delay: uint256, offer_expiration_delay: uint256, ldo_recipients: address[], ldo_allocations: uint256[], ldo_allocations_total: uint256)` initializes the contract and sets the immutable offer parameters.
* `start()` if the offer is not started yet, starts it, reverting unless the smart contract controls enough LDO to execute all purchases. Can be called by anyone.
* `get_allocation(ldo_receiver: address = msg.sender) -> (ldo_alloc: uint256, dai_cost: uint256)` returns the LDO allocation currently available for the given address and its purchase cost in DAI.
* `execute_purchase_for(recipient: address):` will, if there's enough DAI for a purchase allocated to the `recipient` address, assign vested tokens to the recipient by calling the [`TokenManager.assignVested`] function. The vesting start is set to the timestamp of the block the transaction is included to. Reverts unless the `recipient` is a valid LDO recipient, the amount of DAI sent with the call is enough to purchase the whole amount of LDO allocated to the recipient, and the offer is still valid.
* `__default__(): payable` does not allowed.
* `offer_started() -> bool` whether the offer has started.
* `offer_expired() -> bool` whether the offer is no longer valid.
* `recover_unsold_tokens()` given that the offer has expired, transfers all LDO tokens left on the contract to the DAO treasury.

The process is the following:

1. The DAO votes for granting the `ASSIGN_ROLE` to the `PurchaseExecutor` smart contract and transferring out 100_000_000 LDO to that contract. This will allow the contract to transfer these LDO tokens to any address in a vested state.
2. Somebody executes the passed vote and calls `PurchaseExecutor.start()`. Both transactions can be sent from any address.
3. Each purchasers call `approve` function of DAO token to allow `PurchaseExecutor` send tokens to Vault (DAO Agent).
4. Each purchasers call the `PurchaseExecutor.execute_purchase_for` function and receiving the vested LDO tokens. The list of purchasers and their allocated amounts are set during the `PurchaseExecutor` contract deployment.
5. After the offer expires (in one month), `PurchaseExecutor.execute_purchase_for` always reverts. Unsold LDO tokens can be recovered to the DAO treasury by calling a permissionless function.


## Configuration

The offer parameters are set in [`purchasers.csv`] and [`purchase_config.py`]. The first file contains a list of purchaser addresses and the corresponding LDO wei amounts each address is allowed to purchase. The second file contains the following parameters:

* `OFFER_EXPIRATION_DELAY` the delay in seconds between offer start and its expiration.
* `DAI_TO_LDO_RATE` the DAI/LDO rate at which all purchases should be made.
* `VESTING_START_DELAY` the delay in seconds between the purchase and the start of LDO linear unlock. Before this delay has passed, the purchaser address is not allowed to transfer the purchased tokens.
* `VESTING_END_DELAY` the delay in seconds between the purchase and the end of LDO linear unlock. After this delay has passed, the purchaser address is allowed to transfer the full amount of the purchased tokens.
* `ALLOCATIONS_TOTAL` the expected sum of all allocations in [`purchasers.csv`].

[`purchase_config.py`]: ./purchase_config.py
[`purchasers.csv`]: ./purchasers.csv


## Checking the deployed executor

To check that configuration of the deployed executor matches the one specified in [`purchasers.csv`] and [`purchase_config.py`], run the following command, passing the address of the deployed executor via the environment variable:

```
EXECUTOR_ADDRESS=... brownie run scripts/check_deployment.py --network mainnet
```

The script also allows checking that each of the purchasers will actually be able to purchase their allocation. In order to do this, run the script on a forked network on a block where none of the purchasers had actually bought their tokens yet:

```
EXECUTOR_ADDRESS=... brownie run scripts/check_deployment.py --network development
```

You'll need to edit [`brownie-config.yaml`](./brownie-config.yaml) and set the `networks.development.fork` key to an archival node RPC address, optionally suffixed by a `@` followed by a block number to set a specific block to fork from, e.g. `http://node.address:8545@12345`.

When running on a mainnet fork, you can pass and execute the selected votes prior to running the checks by assigning comma-delimited vote IDs list to the `VOTE_IDS` environment variable, e.g.:

```
VOTE_IDS=64,65 EXECUTOR_ADDRESS=... brownie run scripts/check_deployment.py --network development
```
