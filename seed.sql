-- Asset types (e.g. Gold Coins, Diamonds, Loyalty Points)
INSERT INTO assets (id, code, name)
VALUES
    (gen_random_uuid(), 'GOLD', 'Gold Coins'),
    (gen_random_uuid(), 'DIAMONDS', 'Diamonds'),
    (gen_random_uuid(), 'LOYALTY_POINTS', 'Loyalty Points');

-- Users (at least two with initial balances)
INSERT INTO users (id, name)
VALUES
    (gen_random_uuid(), 'Alice'),
    (gen_random_uuid(), 'Bob');

-- System wallets (treasury / revenue account) — one per asset, source/sink for funds
INSERT INTO wallets (id, user_id, asset_id, balance)
SELECT
    gen_random_uuid(),
    NULL,
    a.id,
    100000
FROM assets a;

-- User wallets with initial balances (Alice and Bob, one wallet per asset)
INSERT INTO wallets (id, user_id, asset_id, balance)
SELECT
    gen_random_uuid(),
    u.id,
    a.id,
    CASE
        WHEN u.name = 'Alice' AND a.code = 'GOLD' THEN 100
        WHEN u.name = 'Alice' AND a.code = 'DIAMONDS' THEN 20
        WHEN u.name = 'Alice' AND a.code = 'LOYALTY_POINTS' THEN 500
        WHEN u.name = 'Bob' AND a.code = 'GOLD' THEN 50
        WHEN u.name = 'Bob' AND a.code = 'DIAMONDS' THEN 10
        WHEN u.name = 'Bob' AND a.code = 'LOYALTY_POINTS' THEN 250
        ELSE 0
    END
FROM users u
CROSS JOIN assets a;
