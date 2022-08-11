import csv

# Immutable parameters, don't change these
MAX_PURCHASERS = 50
DAI_TO_LDO_RATE_PRECISION = 10**18
SECONDS_IN_A_DAY = 60 * 60 * 24

#
# Proposal: https://research.lido.fi/t/treasury-diversification-2-part-2/2657
#

# Price terms: 10M LDO for 24,272,320 DAI (2.427232 DAI per LDO)
TOTAL_LDO_SOLD = 10 * 10**6 * 10**18
TOTAL_DAI_PRICE = 24_272_320 * 10**18
DAI_TO_LDO_RATE = DAI_TO_LDO_RATE_PRECISION * TOTAL_LDO_SOLD // TOTAL_DAI_PRICE

# Offer expires in 1 month
OFFER_EXPIRATION_DELAY = SECONDS_IN_A_DAY * 30


def read_csv_purchasers(filename):
    data = [ (item[0], int(item[1])) for item in read_csv_data(filename) ]
    assert len(data) <= MAX_PURCHASERS, f'too many purchasers: max {MAX_PURCHASERS}, got {len(data)}'

    allocations_total = sum([ item[1] for item in data ])
    assert allocations_total == TOTAL_LDO_SOLD, f'invalid total allocation: expected {TOTAL_LDO_SOLD}, actual {allocations_total}'

    return data


def read_csv_data(filename):
    with open(filename, newline='') as csvfile:
        without_comments = (row for row in csvfile if not row.startswith('#'))
        reader = csv.reader(without_comments, delimiter=',', quotechar='"', skipinitialspace=True)
        return list(reader)


LDO_PURCHASERS = read_csv_purchasers('purchasers.csv')
