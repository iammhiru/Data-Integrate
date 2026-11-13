"""Kiem tra Kepware co cho phep WRITE gia tri khong (nhieu cach)."""
from opcua import Client, ua

client = Client("opc.tcp://127.0.0.1:49320", timeout=15)
client.connect()
print("connected")

node_id = "ns=2;s=LINE_01.L01_FILLER_01.CurrentSpeed"
node = client.get_node(node_id)

# 1) Doc AccessLevel / UserAccessLevel
attrs = node.get_attributes([ua.AttributeIds.AccessLevel, ua.AttributeIds.UserAccessLevel,
                             ua.AttributeIds.WriteMask, ua.AttributeIds.Value,
                             ua.AttributeIds.DataType])
for a in attrs:
    print(f"  attr {a.AttributeId}: {a.Value}")

print("current:", node.get_value())

# 2) Ghi bang DataValue chi co Value (khong set status/timestamp)
try:
    dv = ua.DataValue(ua.Variant(12.5, ua.VariantType.Double))
    node.set_data_value(dv)
    print("  set_data_value(only Value) -> OK, now =", node.get_value())
except Exception as e:
    print(f"  set_data_value(only Value) FAIL: {type(e).__name__}: {e}")

# 3) Ghi bang ua.DataValue voi SourceTimestamp/StatusCode bo trong
try:
    dv = ua.DataValue(ua.Variant(13.5, ua.VariantType.Double))
    dv.SourceTimestamp = None
    dv.ServerTimestamp = None
    dv.StatusCode = None
    node.set_data_value(dv)
    print("  set_data_value(None ts/status) -> OK, now =", node.get_value())
except Exception as e:
    print(f"  set_data_value(None ts/status) FAIL: {type(e).__name__}: {e}")

# 4) Ghi thuoc tinh Value truc tiep
try:
    node.set_attribute(ua.AttributeIds.Value, ua.Variant(14.5, ua.VariantType.Double))
    print("  set_attribute(Value) -> OK, now =", node.get_value())
except Exception as e:
    print(f"  set_attribute(Value) FAIL: {type(e).__name__}: {e}")

client.disconnect()
