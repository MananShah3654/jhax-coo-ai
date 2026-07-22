-- Dummy data for owner_id = 5  —  Team page fully populated.
-- Restaurant: "Olympic Flame Burgers"
-- 4 team_members + labor_shifts + orders spread across every date filter bucket.
--
-- Reference date "today" = 2026-07-21 (Tuesday). Weeks start Monday, UTC.
-- Buckets:  today=07-21 | yesterday=07-20 | this_week=07-20..now
--           last_week=07-13..07-19 | this_month=07-01..now | last_month=June
--
-- Every representative day carries the SAME shape so EVERY Team KPI card has data
-- in EVERY bucket:
--   * Maria  -> OVERTIME shift (>8h net)      -> "Overtime Hours" card
--   * James  -> LATE clock-in                 -> "Late Clock-ins" card
--   * David  -> MISSED clock-in               -> "Clock-ins Missed" card
--   * Sofia  -> normal shift
--   * 3 orders/day (revenue)                  -> "Labor Cost %" + "Revenue Per Staff"
-- this_week / this_month are supersets, so they inherit coverage automatically.
--
-- Re-runnable: rows keyed by PK / (owner_id, square_id).
BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Restaurant branch
-- ---------------------------------------------------------------------------
INSERT INTO restaurants (
  id, owner_id, name, city, address, manager, phone,
  square_location_id, is_active, created_at
) VALUES (
  'f5000000-0005-4a00-9000-000000000001', 5, 'Olympic Flame Burgers',
  'Los Angeles', '742 Flame Ave, Los Angeles, CA', 'Maria Gomez',
  '+13105550142', 'OLY_LOC_001', TRUE, NOW()
)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name, city = EXCLUDED.city, address = EXCLUDED.address,
  manager = EXCLUDED.manager, phone = EXCLUDED.phone,
  square_location_id = EXCLUDED.square_location_id, is_active = EXCLUDED.is_active;

-- ---------------------------------------------------------------------------
-- 2) Team members
-- ---------------------------------------------------------------------------
INSERT INTO team_members (
  id, owner_id, restaurant_id, square_id, square_location_id,
  given_name, family_name, email, phone, status, is_owner,
  title, hourly_rate, tax_declared, advance_taken, advance_amount, advance_date,
  created_at, updated_at
) VALUES
  ('f5000000-0005-4a00-9000-000000000101', 5, 'f5000000-0005-4a00-9000-000000000001', 'OLY_TM_MARIA_GOMEZ',   'OLY_LOC_001', 'Maria',  'Gomez',  'maria.gomez@olympicflame.test',  '+13105550101', 'ACTIVE', FALSE, 'Manager',   22.0,  TRUE,  FALSE, NULL,  NULL,       NOW(), NOW()),
  ('f5000000-0005-4a00-9000-000000000102', 5, 'f5000000-0005-4a00-9000-000000000001', 'OLY_TM_JAMES_WILSON',  'OLY_LOC_001', 'James',  'Wilson', 'james.wilson@olympicflame.test', '+13105550102', 'ACTIVE', FALSE, 'Cashier',   17.0,  FALSE, TRUE,  150.0, TIMESTAMPTZ '2026-07-05 10:00:00', NOW(), NOW()),
  ('f5000000-0005-4a00-9000-000000000103', 5, 'f5000000-0005-4a00-9000-000000000001', 'OLY_TM_SOFIA_REYES',   'OLY_LOC_001', 'Sofia',  'Reyes',  'sofia.reyes@olympicflame.test',  '+13105550103', 'ACTIVE', FALSE, 'Chef',      19.5,  TRUE,  FALSE, NULL,  NULL,       NOW(), NOW()),
  ('f5000000-0005-4a00-9000-000000000104', 5, 'f5000000-0005-4a00-9000-000000000001', 'OLY_TM_DAVID_CHEN',    'OLY_LOC_001', 'David',  'Chen',   'david.chen@olympicflame.test',   '+13105550104', 'ACTIVE', FALSE, 'Busser',    16.5,  FALSE, FALSE, NULL,  NULL,       NOW(), NOW())
ON CONFLICT (owner_id, square_id) DO UPDATE SET
  restaurant_id = EXCLUDED.restaurant_id,
  square_location_id = EXCLUDED.square_location_id,
  given_name = EXCLUDED.given_name, family_name = EXCLUDED.family_name,
  email = EXCLUDED.email, phone = EXCLUDED.phone, status = EXCLUDED.status,
  is_owner = EXCLUDED.is_owner, title = EXCLUDED.title,
  hourly_rate = EXCLUDED.hourly_rate, tax_declared = EXCLUDED.tax_declared,
  advance_taken = EXCLUDED.advance_taken, advance_amount = EXCLUDED.advance_amount,
  advance_date = EXCLUDED.advance_date, updated_at = NOW();

-- ---------------------------------------------------------------------------
-- 3) Labor shifts  (clock_in decides which filter bucket a row lands in)
--    Per rep-day: Maria=OT(10h), James=LATE, Sofia=normal, David=MISSED.
-- ---------------------------------------------------------------------------
INSERT INTO labor_shifts (
  id, owner_id, employee_id, restaurant_id, square_id, square_team_member_id,
  square_location_id, clock_in, clock_out, status, declared_tips,
  created_at, updated_at, break_hours, meal_taken, late_clockin, missed_clockin
) VALUES
  -- ===== TODAY (2026-07-21) =====
  ('f5000000-0005-4b00-9000-000000000001', 5, 'f5000000-0005-4a00-9000-000000000101', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0001', 'OLY_TM_MARIA_GOMEZ',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-21 08:00:00', TIMESTAMPTZ '2026-07-21 18:30:00', 'COMPLETED', 95.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000002', 5, 'f5000000-0005-4a00-9000-000000000102', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0002', 'OLY_TM_JAMES_WILSON', 'OLY_LOC_001', TIMESTAMPTZ '2026-07-21 11:15:00', TIMESTAMPTZ '2026-07-21 19:00:00', 'COMPLETED', 120.00, NOW(), NOW(), 0.50, TRUE,  TRUE,  FALSE),
  ('f5000000-0005-4b00-9000-000000000003', 5, 'f5000000-0005-4a00-9000-000000000103', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0003', 'OLY_TM_SOFIA_REYES',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-21 08:00:00', TIMESTAMPTZ '2026-07-21 15:00:00', 'COMPLETED', 88.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000004', 5, 'f5000000-0005-4a00-9000-000000000104', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0004', 'OLY_TM_DAVID_CHEN',   'OLY_LOC_001', TIMESTAMPTZ '2026-07-21 16:00:00', NULL,                             'MISSED',    0.00,   NOW(), NOW(), 0.00, FALSE, FALSE, TRUE),

  -- ===== YESTERDAY (2026-07-20, Mon)  [also feeds THIS WEEK] =====
  ('f5000000-0005-4b00-9000-000000000005', 5, 'f5000000-0005-4a00-9000-000000000101', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0005', 'OLY_TM_MARIA_GOMEZ',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-20 08:00:00', TIMESTAMPTZ '2026-07-20 18:30:00', 'COMPLETED', 90.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000006', 5, 'f5000000-0005-4a00-9000-000000000102', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0006', 'OLY_TM_JAMES_WILSON', 'OLY_LOC_001', TIMESTAMPTZ '2026-07-20 11:20:00', TIMESTAMPTZ '2026-07-20 19:00:00', 'COMPLETED', 105.00, NOW(), NOW(), 0.50, TRUE,  TRUE,  FALSE),
  ('f5000000-0005-4b00-9000-000000000007', 5, 'f5000000-0005-4a00-9000-000000000103', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0007', 'OLY_TM_SOFIA_REYES',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-20 08:00:00', TIMESTAMPTZ '2026-07-20 15:00:00', 'COMPLETED', 82.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000008', 5, 'f5000000-0005-4a00-9000-000000000104', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0008', 'OLY_TM_DAVID_CHEN',   'OLY_LOC_001', TIMESTAMPTZ '2026-07-20 16:00:00', NULL,                             'MISSED',    0.00,   NOW(), NOW(), 0.00, FALSE, FALSE, TRUE),

  -- ===== LAST WEEK (rep day 2026-07-15, Wed) =====
  ('f5000000-0005-4b00-9000-000000000009', 5, 'f5000000-0005-4a00-9000-000000000101', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0009', 'OLY_TM_MARIA_GOMEZ',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-15 08:00:00', TIMESTAMPTZ '2026-07-15 18:30:00', 'COMPLETED', 92.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000010', 5, 'f5000000-0005-4a00-9000-000000000102', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0010', 'OLY_TM_JAMES_WILSON', 'OLY_LOC_001', TIMESTAMPTZ '2026-07-15 11:18:00', TIMESTAMPTZ '2026-07-15 19:00:00', 'COMPLETED', 100.00, NOW(), NOW(), 0.50, TRUE,  TRUE,  FALSE),
  ('f5000000-0005-4b00-9000-000000000011', 5, 'f5000000-0005-4a00-9000-000000000103', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0011', 'OLY_TM_SOFIA_REYES',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-15 08:00:00', TIMESTAMPTZ '2026-07-15 15:00:00', 'COMPLETED', 79.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000012', 5, 'f5000000-0005-4a00-9000-000000000104', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0012', 'OLY_TM_DAVID_CHEN',   'OLY_LOC_001', TIMESTAMPTZ '2026-07-15 16:00:00', NULL,                             'MISSED',    0.00,   NOW(), NOW(), 0.00, FALSE, FALSE, TRUE),

  -- ===== THIS MONTH, earlier (rep day 2026-07-06, Mon — outside this/last week) =====
  ('f5000000-0005-4b00-9000-000000000013', 5, 'f5000000-0005-4a00-9000-000000000101', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0013', 'OLY_TM_MARIA_GOMEZ',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-06 08:00:00', TIMESTAMPTZ '2026-07-06 18:30:00', 'COMPLETED', 90.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000014', 5, 'f5000000-0005-4a00-9000-000000000102', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0014', 'OLY_TM_JAMES_WILSON', 'OLY_LOC_001', TIMESTAMPTZ '2026-07-06 11:22:00', TIMESTAMPTZ '2026-07-06 19:00:00', 'COMPLETED', 98.00,  NOW(), NOW(), 0.50, TRUE,  TRUE,  FALSE),
  ('f5000000-0005-4b00-9000-000000000015', 5, 'f5000000-0005-4a00-9000-000000000103', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0015', 'OLY_TM_SOFIA_REYES',  'OLY_LOC_001', TIMESTAMPTZ '2026-07-06 08:00:00', TIMESTAMPTZ '2026-07-06 15:00:00', 'COMPLETED', 84.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000016', 5, 'f5000000-0005-4a00-9000-000000000104', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0016', 'OLY_TM_DAVID_CHEN',   'OLY_LOC_001', TIMESTAMPTZ '2026-07-06 16:00:00', NULL,                             'MISSED',    0.00,   NOW(), NOW(), 0.00, FALSE, FALSE, TRUE),

  -- ===== LAST MONTH (rep day 2026-06-16, Tue) =====
  ('f5000000-0005-4b00-9000-000000000017', 5, 'f5000000-0005-4a00-9000-000000000101', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0017', 'OLY_TM_MARIA_GOMEZ',  'OLY_LOC_001', TIMESTAMPTZ '2026-06-16 08:00:00', TIMESTAMPTZ '2026-06-16 18:30:00', 'COMPLETED', 88.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000018', 5, 'f5000000-0005-4a00-9000-000000000102', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0018', 'OLY_TM_JAMES_WILSON', 'OLY_LOC_001', TIMESTAMPTZ '2026-06-16 11:25:00', TIMESTAMPTZ '2026-06-16 19:00:00', 'COMPLETED', 96.00,  NOW(), NOW(), 0.50, TRUE,  TRUE,  FALSE),
  ('f5000000-0005-4b00-9000-000000000019', 5, 'f5000000-0005-4a00-9000-000000000103', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0019', 'OLY_TM_SOFIA_REYES',  'OLY_LOC_001', TIMESTAMPTZ '2026-06-16 08:00:00', TIMESTAMPTZ '2026-06-16 15:00:00', 'COMPLETED', 77.00,  NOW(), NOW(), 0.50, TRUE,  FALSE, FALSE),
  ('f5000000-0005-4b00-9000-000000000020', 5, 'f5000000-0005-4a00-9000-000000000104', 'f5000000-0005-4a00-9000-000000000001', 'OLY_SH_0020', 'OLY_TM_DAVID_CHEN',   'OLY_LOC_001', TIMESTAMPTZ '2026-06-16 16:00:00', NULL,                             'MISSED',    0.00,   NOW(), NOW(), 0.00, FALSE, FALSE, TRUE)
ON CONFLICT (owner_id, square_id) DO UPDATE SET
  employee_id = EXCLUDED.employee_id,
  restaurant_id = EXCLUDED.restaurant_id,
  square_team_member_id = EXCLUDED.square_team_member_id,
  square_location_id = EXCLUDED.square_location_id,
  clock_in = EXCLUDED.clock_in, clock_out = EXCLUDED.clock_out,
  status = EXCLUDED.status, declared_tips = EXCLUDED.declared_tips,
  break_hours = EXCLUDED.break_hours, meal_taken = EXCLUDED.meal_taken,
  late_clockin = EXCLUDED.late_clockin, missed_clockin = EXCLUDED.missed_clockin,
  updated_at = NOW();

-- ---------------------------------------------------------------------------
-- 4) Orders  (revenue -> powers "Labor Cost %" and "Revenue Per Staff" cards)
--    3 orders on each rep day; placed_at decides the bucket.
--    Per-day revenue ~= $1,722 vs ~$470 wages -> labor ~27% (healthy),
--    revenue/hour ~= $72 (Good).
-- ---------------------------------------------------------------------------
INSERT INTO orders (
  id, owner_id, restaurant_id, customer_id, placed_at, channel,
  subtotal, tax, tip, total, wait_minutes, rating
) VALUES
  -- TODAY 2026-07-21
  ('f5000000-0005-4c00-9000-000000000001', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-21 12:30:00', 'Dine In',  480.00, 43.20, 72.00, 595.20, 12, 5),
  ('f5000000-0005-4c00-9000-000000000002', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-21 13:45:00', 'Takeout',  560.00, 50.40, 84.00, 694.40,  8, 4),
  ('f5000000-0005-4c00-9000-000000000003', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-21 18:10:00', 'Delivery', 360.00, 32.40, 40.00, 432.80, 20, 5),
  -- YESTERDAY 2026-07-20
  ('f5000000-0005-4c00-9000-000000000004', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-20 12:15:00', 'Dine In',  520.00, 46.80, 78.00, 644.80, 10, 5),
  ('f5000000-0005-4c00-9000-000000000005', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-20 14:05:00', 'Takeout',  440.00, 39.60, 55.00, 534.60,  9, 4),
  ('f5000000-0005-4c00-9000-000000000006', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-20 19:20:00', 'Delivery', 400.00, 36.00, 48.00, 484.00, 22, 5),
  -- LAST WEEK 2026-07-15
  ('f5000000-0005-4c00-9000-000000000007', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-15 12:40:00', 'Dine In',  500.00, 45.00, 75.00, 620.00, 11, 5),
  ('f5000000-0005-4c00-9000-000000000008', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-15 13:55:00', 'Takeout',  580.00, 52.20, 87.00, 719.20,  7, 4),
  ('f5000000-0005-4c00-9000-000000000009', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-15 18:30:00', 'Delivery', 340.00, 30.60, 38.00, 408.60, 19, 5),
  -- EARLIER THIS MONTH 2026-07-06
  ('f5000000-0005-4c00-9000-000000000010', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-06 12:20:00', 'Dine In',  460.00, 41.40, 69.00, 570.40, 13, 5),
  ('f5000000-0005-4c00-9000-000000000011', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-06 14:10:00', 'Takeout',  540.00, 48.60, 81.00, 669.60,  8, 4),
  ('f5000000-0005-4c00-9000-000000000012', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-07-06 18:45:00', 'Delivery', 380.00, 34.20, 42.00, 456.20, 21, 5),
  -- LAST MONTH 2026-06-16
  ('f5000000-0005-4c00-9000-000000000013', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-06-16 12:35:00', 'Dine In',  510.00, 45.90, 76.00, 631.90, 12, 5),
  ('f5000000-0005-4c00-9000-000000000014', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-06-16 13:50:00', 'Takeout',  550.00, 49.50, 82.00, 681.50,  9, 4),
  ('f5000000-0005-4c00-9000-000000000015', 5, 'f5000000-0005-4a00-9000-000000000001', NULL, TIMESTAMPTZ '2026-06-16 18:25:00', 'Delivery', 350.00, 31.50, 39.00, 420.50, 20, 5)
ON CONFLICT (id) DO NOTHING;

COMMIT;
