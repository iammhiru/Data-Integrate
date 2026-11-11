-- Master data mau: 100 may, 5 san pham, 3 ca.

INSERT INTO machine (machine_id, machine_name, line, machine_type, location, ideal_speed, installed_at)
SELECT 'M' || lpad(i::text, 3, '0'),
       'Machine ' || lpad(i::text, 3, '0'),
       'LINE-' || ((i - 1) / 20 + 1),
       (ARRAY['CNC', 'PRESS', 'INJECTION', 'PACKING'])[(i % 4) + 1],
       'Plant-1',
       1500,
       DATE '2024-01-01'
FROM generate_series(1, 100) AS i
ON CONFLICT DO NOTHING;

-- Moi nguon dat ten ID khac nhau -> middleware tra bang nay de chuan hoa ve machine_id
INSERT INTO machine_id_mapping (source, source_id, machine_id)
SELECT s.source,
       CASE s.source
           WHEN 'kepware-opcua'  THEN 'Line' || ((i - 1) / 20 + 1) || '.M' || lpad(i::text, 3, '0')
           WHEN 'production-sim' THEN 'MC-' || lpad(i::text, 3, '0')
           WHEN 'quality-sim'    THEN 'EQ' || lpad(i::text, 4, '0')
       END,
       'M' || lpad(i::text, 3, '0')
FROM generate_series(1, 100) AS i
CROSS JOIN (VALUES ('kepware-opcua'), ('production-sim'), ('quality-sim')) AS s(source)
ON CONFLICT DO NOTHING;

INSERT INTO product (product_id, product_name, ideal_cycle_time_sec) VALUES
    ('P01', 'Bracket A',   2.0),
    ('P02', 'Bracket B',   2.5),
    ('P03', 'Housing C',   4.0),
    ('P04', 'Cover D',     3.0),
    ('P05', 'Gear E',      5.0)
ON CONFLICT DO NOTHING;

INSERT INTO shift (shift_id, shift_name, start_time, end_time, planned_minutes, planned_break_minutes) VALUES
    ('A', 'Morning',   '06:00', '14:00', 480, 30),
    ('B', 'Afternoon', '14:00', '22:00', 480, 30),
    ('C', 'Night',     '22:00', '06:00', 480, 30)
ON CONFLICT DO NOTHING;
