// ============================================================================
//  AUTO-GENERATED — DO NOT EDIT
//  Nguồn: IndustrialTelemetry.Middleware/metadata/catalog.json
//  Sinh bởi: tools/gen_ui_catalog.py
//  Regenerate: python tools/gen_ui_catalog.py
// ============================================================================

export type TagDef = {
  name: string;
  dataType: string;
  unit: string | null;
  tagType: string;
  tagCode: string;
  meaning: string;
};

export type MachineDef = {
  machineId: string;
  machineType: string;
  equipmentCode: string;
  channel: string;
  lineId: string;
  processId: string;
  tags: TagDef[];
};

export const PLANT_ID = "PLANT_01";
export const TOTAL_TAGS = 404;
export const TOTAL_MACHINES = 26;
export const MACHINES: MachineDef[] = [
  {
    "machineId": "L01_PREFEED_01",
    "machineType": "PREFORM_FEEDER",
    "equipmentCode": "PREF-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "PREFORM_FEEDING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "PreformFeedRate",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L01.PREFORMFEEDRATE",
        "meaning": "Tan suat cap preform thuc te"
      },
      {
        "name": "HopperLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "PREF.L01.HOPPERLEVEL",
        "meaning": "Muc thay the trong hopper"
      },
      {
        "name": "HopperLevelLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L01.HOPPERLEVELLOW",
        "meaning": "True khi muc hopper duoi nguong can bo sung"
      }
    ]
  },
  {
    "machineId": "L01_BLOWER_01",
    "machineType": "STRETCH_BLOW_MOULDER",
    "equipmentCode": "BLOW-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "BLOW_MOULDING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CycleTime",
        "dataType": "Float",
        "unit": "s",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.CYCLETIME",
        "meaning": "Thoi gian mot chu ky thoi chai"
      },
      {
        "name": "BlowPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.BLOWPRESSURE",
        "meaning": "Ap suat thoi trong khu thoi chai"
      },
      {
        "name": "HeaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.HEATERTEMP",
        "meaning": "Nhiet do heater thoi PET"
      },
      {
        "name": "MoldTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.MOLDTEMP",
        "meaning": "Nhiet do khuon"
      },
      {
        "name": "CavityCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L01.CAVITYCOUNT",
        "meaning": "So khuon ep trong khuon"
      },
      {
        "name": "BottleWeight",
        "dataType": "Float",
        "unit": "g",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.BOTTLEWEIGHT",
        "meaning": "Khoi luong chai rong"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L01.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu tinh theo moc thoi gian"
      }
    ]
  },
  {
    "machineId": "L01_AIRCONV_01",
    "machineType": "AIR_CONVEYOR",
    "equipmentCode": "ACONV-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "BOTTLE_CONVEYING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "m/min",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "m/min",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "AirPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.AIRPRESSURE",
        "meaning": "Ap suat duong cap khi nen"
      },
      {
        "name": "AirFlowRate",
        "dataType": "Float",
        "unit": "Nm3/h",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.AIRFLOWRATE",
        "meaning": "Lu luong khi nen"
      },
      {
        "name": "MotorSpeed",
        "dataType": "Float",
        "unit": "rpm",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.MOTORSPEED",
        "meaning": "Toc do dong co hanh"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L01.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu"
      }
    ]
  },
  {
    "machineId": "L01_RINSER_01",
    "machineType": "BOTTLE_RINSER",
    "equipmentCode": "RINSE-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "RINSING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "RinseWaterPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.RINSEWATERPRESSURE",
        "meaning": "Ap suat nuoc rua"
      },
      {
        "name": "RinseWaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.RINSEWATERTEMP",
        "meaning": "Nhiet do nuoc rua"
      },
      {
        "name": "RinseWaterFlowRate",
        "dataType": "Float",
        "unit": "m3/h",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.RINSEWATERFLOWRATE",
        "meaning": "Lu luong nuoc rua"
      },
      {
        "name": "NozzlePressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L01.NOZZLEPRESSURE",
        "meaning": "Ap suat vo phun"
      },
      {
        "name": "CIPPhase",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L01.CIPPHASE",
        "meaning": "Pha CIP hien tai (enum muc 0-4)"
      }
    ]
  },
  {
    "machineId": "L01_FILLER_01",
    "machineType": "CARBONATED_FILLER",
    "equipmentCode": "FILL-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "FILLING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "FillLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.FILLLEVEL",
        "meaning": "Muc chiet rot chai"
      },
      {
        "name": "FillRate",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.FILLRATE",
        "meaning": "Toc do chiet rot thuc te"
      },
      {
        "name": "HeadCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L01.HEADCOUNT",
        "meaning": "So dau chiet"
      },
      {
        "name": "CO2Pressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.CO2PRESSURE",
        "meaning": "Ap suat CO2"
      },
      {
        "name": "CO2FlowRate",
        "dataType": "Float",
        "unit": "Nm3/h",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.CO2FLOWRATE",
        "meaning": "Lu luong CO2"
      },
      {
        "name": "ProductTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.PRODUCTTEMP",
        "meaning": "Nhiet do san pham"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "FILL.L01.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu"
      }
    ]
  },
  {
    "machineId": "L01_CAPPER_01",
    "machineType": "SCREW_CAPPER",
    "equipmentCode": "CAPP-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "CAPPING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "Torque",
        "dataType": "Float",
        "unit": "Nm",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L01.TORQUE",
        "meaning": "Mo-men xoan van nap"
      },
      {
        "name": "CapFeedRate",
        "dataType": "Float",
        "unit": "caps/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L01.CAPFEEDRATE",
        "meaning": "Tan suat cap nap"
      },
      {
        "name": "CapMissing",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.CAPMISSING",
        "meaning": "True khi phat hien thieu nap"
      },
      {
        "name": "TorqueHigh",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L01.TORQUEHIGH",
        "meaning": "True khi mo-men van nap vuot nguong"
      }
    ]
  },
  {
    "machineId": "L01_LABELER_01",
    "machineType": "BOTTLE_LABELER",
    "equipmentCode": "LABL-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "LABELLING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "LABL.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "LABL.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "LabelRollRemaining",
        "dataType": "Float",
        "unit": "m",
        "tagType": "ANALOG",
        "tagCode": "LABL.L01.LABELROLLREMAINING",
        "meaning": "Chieu dai cuon nhan con lai"
      },
      {
        "name": "LabelApplyCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L01.LABELAPPLYCOUNT",
        "meaning": "So nhan da dan"
      },
      {
        "name": "LabelMissing",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.LABELMISSING",
        "meaning": "True khi phat hien thieu nhan"
      },
      {
        "name": "LabelRollLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L01.LABELROLLLOW",
        "meaning": "True khi cuon nhan sap het"
      }
    ]
  },
  {
    "machineId": "L01_CODER_01",
    "machineType": "DATE_CODER",
    "equipmentCode": "CODE-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "CODING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "PrintCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L01.PRINTCOUNT",
        "meaning": "So ma da in"
      },
      {
        "name": "InkLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "CODE.L01.INKLEVEL",
        "meaning": "Muc muc in"
      },
      {
        "name": "InkLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.INKLOW",
        "meaning": "True khi muc muc thap"
      },
      {
        "name": "PrintQuality",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L01.PRINTQUALITY",
        "meaning": "Chat luong in (enum muc 0-2)"
      },
      {
        "name": "NozzleHeight",
        "dataType": "Float",
        "unit": "mm",
        "tagType": "ANALOG",
        "tagCode": "CODE.L01.NOZZLEHEIGHT",
        "meaning": "Do cao voi phun"
      }
    ]
  },
  {
    "machineId": "L01_CASEPACKER_01",
    "machineType": "CASE_PACKER",
    "equipmentCode": "CASE-L01-01",
    "channel": "LINE_01",
    "lineId": "LINE_01",
    "processId": "CASE_PACKING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L01.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L01.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L01.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L01.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L01.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CaseCount",
        "dataType": "Long",
        "unit": "cases",
        "tagType": "COUNTER",
        "tagCode": "CASE.L01.CASECOUNT",
        "meaning": "So thung da dong"
      },
      {
        "name": "BottlesPerCase",
        "dataType": "Int",
        "unit": "pcs",
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.BOTTLESPERCASE",
        "meaning": "So chai trong mot thung"
      },
      {
        "name": "CaseFormat",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.CASEFORMAT",
        "meaning": "Dinh dang thung (enum muc 0-2)"
      },
      {
        "name": "PalletCount",
        "dataType": "Long",
        "unit": "pallets",
        "tagType": "COUNTER",
        "tagCode": "CASE.L01.PALLETCOUNT",
        "meaning": "So pallet da tao"
      },
      {
        "name": "FilmRemaining",
        "dataType": "Float",
        "unit": "m",
        "tagType": "ANALOG",
        "tagCode": "CASE.L01.FILMREMAINING",
        "meaning": "Chieu dai mang goi con lai"
      },
      {
        "name": "FilmLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.FILMLOW",
        "meaning": "True khi mang goi sap het"
      },
      {
        "name": "CaseJam",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L01.CASEJAM",
        "meaning": "True khi phat hien ket thung"
      }
    ]
  },
  {
    "machineId": "L02_PREFEED_01",
    "machineType": "PREFORM_FEEDER",
    "equipmentCode": "PREF-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "PREFORM_FEEDING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "PREF.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "PreformFeedRate",
        "dataType": "Float",
        "unit": "preform/min",
        "tagType": "ANALOG",
        "tagCode": "PREF.L02.PREFORMFEEDRATE",
        "meaning": "Tan suat cap preform thuc te"
      },
      {
        "name": "HopperLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "PREF.L02.HOPPERLEVEL",
        "meaning": "Muc thay the trong hopper"
      },
      {
        "name": "HopperLevelLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "PREF.L02.HOPPERLEVELLOW",
        "meaning": "True khi muc hopper duoi nguong can bo sung"
      }
    ]
  },
  {
    "machineId": "L02_BLOWER_01",
    "machineType": "STRETCH_BLOW_MOULDER",
    "equipmentCode": "BLOW-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "BLOW_MOULDING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "BLOW.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CycleTime",
        "dataType": "Float",
        "unit": "s",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.CYCLETIME",
        "meaning": "Thoi gian mot chu ky thoi chai"
      },
      {
        "name": "BlowPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.BLOWPRESSURE",
        "meaning": "Ap suat thoi trong khu thoi chai"
      },
      {
        "name": "HeaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.HEATERTEMP",
        "meaning": "Nhiet do heater thoi PET"
      },
      {
        "name": "MoldTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.MOLDTEMP",
        "meaning": "Nhiet do khuon"
      },
      {
        "name": "CavityCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "BLOW.L02.CAVITYCOUNT",
        "meaning": "So khuon ep trong khuon"
      },
      {
        "name": "BottleWeight",
        "dataType": "Float",
        "unit": "g",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.BOTTLEWEIGHT",
        "meaning": "Khoi luong chai rong"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "BLOW.L02.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu tinh theo moc thoi gian"
      }
    ]
  },
  {
    "machineId": "L02_AIRCONV_01",
    "machineType": "AIR_CONVEYOR",
    "equipmentCode": "ACONV-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "BOTTLE_CONVEYING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "ACONV.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "m/min",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "m/min",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "ACONV.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "AirPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.AIRPRESSURE",
        "meaning": "Ap suat duong cap khi nen"
      },
      {
        "name": "AirFlowRate",
        "dataType": "Float",
        "unit": "Nm3/h",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.AIRFLOWRATE",
        "meaning": "Lu luong khi nen"
      },
      {
        "name": "MotorSpeed",
        "dataType": "Float",
        "unit": "rpm",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.MOTORSPEED",
        "meaning": "Toc do dong co hanh"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "ACONV.L02.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu"
      }
    ]
  },
  {
    "machineId": "L02_RINSER_01",
    "machineType": "BOTTLE_RINSER",
    "equipmentCode": "RINSE-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "RINSING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "RinseWaterPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.RINSEWATERPRESSURE",
        "meaning": "Ap suat nuoc rua"
      },
      {
        "name": "RinseWaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.RINSEWATERTEMP",
        "meaning": "Nhiet do nuoc rua"
      },
      {
        "name": "RinseWaterFlowRate",
        "dataType": "Float",
        "unit": "m3/h",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.RINSEWATERFLOWRATE",
        "meaning": "Lu luong nuoc rua"
      },
      {
        "name": "NozzlePressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L02.NOZZLEPRESSURE",
        "meaning": "Ap suat vo phun"
      },
      {
        "name": "CIPPhase",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L02.CIPPHASE",
        "meaning": "Pha CIP hien tai (enum muc 0-4)"
      }
    ]
  },
  {
    "machineId": "L02_FILLER_01",
    "machineType": "STILL_FILLER",
    "equipmentCode": "FILL-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "FILLING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "FillLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.FILLLEVEL",
        "meaning": "Muc chiet rot chai"
      },
      {
        "name": "FillRate",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.FILLRATE",
        "meaning": "Toc do chiet rot thuc te"
      },
      {
        "name": "HeadCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L02.HEADCOUNT",
        "meaning": "So dau chiet"
      },
      {
        "name": "WaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.WATERTEMP",
        "meaning": "Nhiet do nuoc chiet"
      },
      {
        "name": "WaterConductivity",
        "dataType": "Float",
        "unit": "uS/cm",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.WATERCONDUCTIVITY",
        "meaning": "Do dan nuoc"
      },
      {
        "name": "FillingPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.FILLINGPRESSURE",
        "meaning": "Ap suat trong qua trinh chiet"
      },
      {
        "name": "ProductTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "FILL.L02.PRODUCTTEMP",
        "meaning": "Nhiet do san pham"
      }
    ]
  },
  {
    "machineId": "L02_CAPPER_01",
    "machineType": "SCREW_CAPPER",
    "equipmentCode": "CAPP-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "CAPPING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CAPP.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "Torque",
        "dataType": "Float",
        "unit": "Nm",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L02.TORQUE",
        "meaning": "Mo-men xoan van nap"
      },
      {
        "name": "CapFeedRate",
        "dataType": "Float",
        "unit": "caps/min",
        "tagType": "ANALOG",
        "tagCode": "CAPP.L02.CAPFEEDRATE",
        "meaning": "Tan suat cap nap"
      },
      {
        "name": "CapMissing",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.CAPMISSING",
        "meaning": "True khi phat hien thieu nap"
      },
      {
        "name": "TorqueHigh",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CAPP.L02.TORQUEHIGH",
        "meaning": "True khi mo-men van nap vuot nguong"
      }
    ]
  },
  {
    "machineId": "L02_LABELER_01",
    "machineType": "BOTTLE_LABELER",
    "equipmentCode": "LABL-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "LABELLING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "LABL.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "bottles/min",
        "tagType": "ANALOG",
        "tagCode": "LABL.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "LabelRollRemaining",
        "dataType": "Float",
        "unit": "m",
        "tagType": "ANALOG",
        "tagCode": "LABL.L02.LABELROLLREMAINING",
        "meaning": "Chieu dai cuon nhan con lai"
      },
      {
        "name": "LabelApplyCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "LABL.L02.LABELAPPLYCOUNT",
        "meaning": "So nhan da dan"
      },
      {
        "name": "LabelMissing",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.LABELMISSING",
        "meaning": "True khi phat hien thieu nhan"
      },
      {
        "name": "LabelRollLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "LABL.L02.LABELROLLLOW",
        "meaning": "True khi cuon nhan sap het"
      }
    ]
  },
  {
    "machineId": "L02_CODER_01",
    "machineType": "DATE_CODER",
    "equipmentCode": "CODE-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "CODING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "PrintCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L02.PRINTCOUNT",
        "meaning": "So ma da in"
      },
      {
        "name": "InkLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "CODE.L02.INKLEVEL",
        "meaning": "Muc muc in"
      },
      {
        "name": "InkLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.INKLOW",
        "meaning": "True khi muc muc thap"
      },
      {
        "name": "PrintQuality",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L02.PRINTQUALITY",
        "meaning": "Chat luong in (enum muc 0-2)"
      },
      {
        "name": "NozzleHeight",
        "dataType": "Float",
        "unit": "mm",
        "tagType": "ANALOG",
        "tagCode": "CODE.L02.NOZZLEHEIGHT",
        "meaning": "Do cao voi phun"
      }
    ]
  },
  {
    "machineId": "L02_CASEPACKER_01",
    "machineType": "CASE_PACKER",
    "equipmentCode": "CASE-L02-01",
    "channel": "LINE_02",
    "lineId": "LINE_02",
    "processId": "CASE_PACKING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L02.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L02.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L02.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L02.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L02.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CaseCount",
        "dataType": "Long",
        "unit": "cases",
        "tagType": "COUNTER",
        "tagCode": "CASE.L02.CASECOUNT",
        "meaning": "So thung da dong"
      },
      {
        "name": "BottlesPerCase",
        "dataType": "Int",
        "unit": "pcs",
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.BOTTLESPERCASE",
        "meaning": "So chai trong mot thung"
      },
      {
        "name": "CaseFormat",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.CASEFORMAT",
        "meaning": "Dinh dang thung (enum muc 0-2)"
      },
      {
        "name": "PalletCount",
        "dataType": "Long",
        "unit": "pallets",
        "tagType": "COUNTER",
        "tagCode": "CASE.L02.PALLETCOUNT",
        "meaning": "So pallet da tao"
      },
      {
        "name": "FilmRemaining",
        "dataType": "Float",
        "unit": "m",
        "tagType": "ANALOG",
        "tagCode": "CASE.L02.FILMREMAINING",
        "meaning": "Chieu dai mang goi con lai"
      },
      {
        "name": "FilmLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.FILMLOW",
        "meaning": "True khi mang goi sap het"
      },
      {
        "name": "CaseJam",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L02.CASEJAM",
        "meaning": "True khi phat hien ket thung"
      }
    ]
  },
  {
    "machineId": "L03_CANDEPAL_01",
    "machineType": "CAN_DEPALLETIZER",
    "equipmentCode": "DEPL-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "CAN_DEPALLETTIZING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "DEPL.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "DEPL.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "DEPL.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "DEPL.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "DEPL.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CanFeedRate",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "DEPL.L03.CANFEEDRATE",
        "meaning": "Tan suat cap lon"
      },
      {
        "name": "LayerCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.LAYERCOUNT",
        "meaning": "So lop lon tren pallet"
      },
      {
        "name": "PalletCount",
        "dataType": "Long",
        "unit": "pallets",
        "tagType": "COUNTER",
        "tagCode": "DEPL.L03.PALLETCOUNT",
        "meaning": "So pallet da xu ly"
      },
      {
        "name": "GripperFault",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "DEPL.L03.GRIPPERFAULT",
        "meaning": "True khi co loi co gia"
      }
    ]
  },
  {
    "machineId": "L03_CANRINSER_01",
    "machineType": "CAN_RINSER",
    "equipmentCode": "RINSE-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "RINSING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "RINSE.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "RinseWaterPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.RINSEWATERPRESSURE",
        "meaning": "Ap suat nuoc rua"
      },
      {
        "name": "RinseWaterTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.RINSEWATERTEMP",
        "meaning": "Nhiet do nuoc rua"
      },
      {
        "name": "RinseWaterFlowRate",
        "dataType": "Float",
        "unit": "m3/h",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.RINSEWATERFLOWRATE",
        "meaning": "Lu luong nuoc rua"
      },
      {
        "name": "NozzlePressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "RINSE.L03.NOZZLEPRESSURE",
        "meaning": "Ap suat vo phun"
      },
      {
        "name": "CIPPhase",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "RINSE.L03.CIPPHASE",
        "meaning": "Pha CIP hien tai (enum muc 0-4)"
      }
    ]
  },
  {
    "machineId": "L03_CANFILLER_01",
    "machineType": "CAN_FILLER",
    "equipmentCode": "FILL-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "FILLING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "FILL.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "FillLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.FILLLEVEL",
        "meaning": "Muc chiet lon"
      },
      {
        "name": "FillRate",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.FILLRATE",
        "meaning": "Toc do chiet lon thuc te"
      },
      {
        "name": "HeadCount",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "FILL.L03.HEADCOUNT",
        "meaning": "So dau chiet"
      },
      {
        "name": "CO2Pressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.CO2PRESSURE",
        "meaning": "Ap suat CO2"
      },
      {
        "name": "CO2FlowRate",
        "dataType": "Float",
        "unit": "Nm3/h",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.CO2FLOWRATE",
        "meaning": "Lu luong CO2"
      },
      {
        "name": "ProductTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.PRODUCTTEMP",
        "meaning": "Nhiet do san pham"
      },
      {
        "name": "PowerConsumption",
        "dataType": "Float",
        "unit": "kW",
        "tagType": "ANALOG",
        "tagCode": "FILL.L03.POWERCONSUMPTION",
        "meaning": "Cong suat tieu thu"
      }
    ]
  },
  {
    "machineId": "L03_SEAMER_01",
    "machineType": "CAN_SEAMER",
    "equipmentCode": "SEAM-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "SEAMING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "SEAM.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "SEAM.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "SEAM.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "SEAM.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "SEAM.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "SeamTorque",
        "dataType": "Float",
        "unit": "Nm",
        "tagType": "ANALOG",
        "tagCode": "SEAM.L03.SEAMTORQUE",
        "meaning": "Mo-men xoan tao duong bien"
      },
      {
        "name": "SeamPressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "SEAM.L03.SEAMPRESSURE",
        "meaning": "Ap suat tao duong bien"
      },
      {
        "name": "SeamQuality",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "SEAM.L03.SEAMQUALITY",
        "meaning": "Chat luong duong bien (enum muc 0-2)"
      },
      {
        "name": "SeamDefectCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "SEAM.L03.SEAMDEFECTCOUNT",
        "meaning": "So duong bien khong dat"
      },
      {
        "name": "CanVacuum",
        "dataType": "Float",
        "unit": "kPa",
        "tagType": "ANALOG",
        "tagCode": "SEAM.L03.CANVACUUM",
        "meaning": "Ap suat chan khong trong lon"
      }
    ]
  },
  {
    "machineId": "L03_CANCODER_01",
    "machineType": "DATE_CODER",
    "equipmentCode": "CODE-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "CODING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "pcs/min",
        "tagType": "ANALOG",
        "tagCode": "CODE.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "PrintCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CODE.L03.PRINTCOUNT",
        "meaning": "So ma da in"
      },
      {
        "name": "InkLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "CODE.L03.INKLEVEL",
        "meaning": "Muc muc in"
      },
      {
        "name": "InkLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.INKLOW",
        "meaning": "True khi muc muc thap"
      },
      {
        "name": "PrintQuality",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CODE.L03.PRINTQUALITY",
        "meaning": "Chat luong in (enum muc 0-2)"
      },
      {
        "name": "NozzleHeight",
        "dataType": "Float",
        "unit": "mm",
        "tagType": "ANALOG",
        "tagCode": "CODE.L03.NOZZLEHEIGHT",
        "meaning": "Do cao voi phun"
      }
    ]
  },
  {
    "machineId": "L03_CANINSPECT_01",
    "machineType": "CAN_INSPECTION",
    "equipmentCode": "INSP-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "INSPECTION",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "INSP.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cans/min",
        "tagType": "ANALOG",
        "tagCode": "INSP.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "INSP.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "INSP.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "INSP.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "InspectionCount",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "INSP.L03.INSPECTIONCOUNT",
        "meaning": "So lon da kiem tra"
      },
      {
        "name": "DefectRate",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "INSP.L03.DEFECTRATE",
        "meaning": "Ty le loi cua hang gan nhat"
      },
      {
        "name": "InspectResult",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.INSPECTRESULT",
        "meaning": "Ket qua kiem tra (enum muc 0-2)"
      },
      {
        "name": "RejectReason",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.REJECTREASON",
        "meaning": "Ly do loai (enum muc 0-4)"
      },
      {
        "name": "CameraFault",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "INSP.L03.CAMERAFAULT",
        "meaning": "True khi loi camera kiem tra"
      }
    ]
  },
  {
    "machineId": "L03_CASEPACKER_01",
    "machineType": "CASE_PACKER",
    "equipmentCode": "CASE-L03-01",
    "channel": "LINE_03",
    "lineId": "LINE_03",
    "processId": "CASE_PACKING",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "CurrentSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L03.CURRENTSPEED",
        "meaning": "Toc do thuc te hien tai; ve 0 khi may dung"
      },
      {
        "name": "DesignSpeed",
        "dataType": "Float",
        "unit": "cases/min",
        "tagType": "ANALOG",
        "tagCode": "CASE.L03.DESIGNSPEED",
        "meaning": "Toc do thiet ke / dinh muc mo phong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L03.TOTALCOUNTER",
        "meaning": "Tong so don vi may da xu ly, tich luy"
      },
      {
        "name": "GoodCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L03.GOODCOUNTER",
        "meaning": "So don vi dat theo logic may"
      },
      {
        "name": "DefectCounter",
        "dataType": "Long",
        "unit": "pcs",
        "tagType": "COUNTER",
        "tagCode": "CASE.L03.DEFECTCOUNTER",
        "meaning": "So don vi loi / loai ra do may ghi nhan"
      },
      {
        "name": "Starved",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.STARVED",
        "meaning": "True khi may thieu san pham / nguyen lieu dau vao"
      },
      {
        "name": "Blocked",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.BLOCKED",
        "meaning": "True khi dau ra may bi chan do cong doan sau hoac buffer day"
      },
      {
        "name": "CaseCount",
        "dataType": "Long",
        "unit": "cases",
        "tagType": "COUNTER",
        "tagCode": "CASE.L03.CASECOUNT",
        "meaning": "So thung da dong"
      },
      {
        "name": "CansPerCase",
        "dataType": "Int",
        "unit": "pcs",
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.CANSPERCASE",
        "meaning": "So lon trong mot thung"
      },
      {
        "name": "CaseFormat",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.CASEFORMAT",
        "meaning": "Dinh dang thung (enum muc 0-2)"
      },
      {
        "name": "PalletCount",
        "dataType": "Long",
        "unit": "pallets",
        "tagType": "COUNTER",
        "tagCode": "CASE.L03.PALLETCOUNT",
        "meaning": "So pallet da tao"
      },
      {
        "name": "FilmRemaining",
        "dataType": "Float",
        "unit": "m",
        "tagType": "ANALOG",
        "tagCode": "CASE.L03.FILMREMAINING",
        "meaning": "Chieu dai mang goi con lai"
      },
      {
        "name": "FilmLow",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.FILMLOW",
        "meaning": "True khi mang goi sap het"
      },
      {
        "name": "CaseJam",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CASE.L03.CASEJAM",
        "meaning": "True khi phat hien ket thung"
      }
    ]
  },
  {
    "machineId": "CIP_SKID_01",
    "machineType": "CIP_SKID",
    "equipmentCode": "CIP-SHARED-01",
    "channel": "SHARED",
    "lineId": "SHARED",
    "processId": "CIP",
    "tags": [
      {
        "name": "MachineState",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.MACHINESTATE",
        "meaning": "Trang thai may (enum muc 0-5)"
      },
      {
        "name": "MachineMode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.MACHINEMODE",
        "meaning": "Che do dieu khien: 0 OFF, 1 MANUAL, 2 AUTO, 3 MAINTENANCE"
      },
      {
        "name": "EmergencyStop",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.EMERGENCYSTOP",
        "meaning": "True khi mach dung khanh dang tac dong"
      },
      {
        "name": "AlarmCode",
        "dataType": "Int",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.ALARMCODE",
        "meaning": "0 = khong co alarm; gia tri khac 0 la ma alarm dang hoat dong"
      },
      {
        "name": "TotalCounter",
        "dataType": "Long",
        "unit": "cycles",
        "tagType": "COUNTER",
        "tagCode": "CIP.SHD.TOTALCOUNTER",
        "meaning": "Tong so chu ky CIP da chay"
      },
      {
        "name": "TankTemp",
        "dataType": "Float",
        "unit": "degC",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.TANKTEMP",
        "meaning": "Nhiet do be chua CIP"
      },
      {
        "name": "TankLevel",
        "dataType": "Float",
        "unit": "%",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.TANKLEVEL",
        "meaning": "Muc be chua CIP"
      },
      {
        "name": "Conductivity",
        "dataType": "Float",
        "unit": "uS/cm",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.CONDUCTIVITY",
        "meaning": "Do dan dung dich CIP"
      },
      {
        "name": "pH",
        "dataType": "Float",
        "unit": "pH",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.PH",
        "meaning": "Chi so pH cua dung dich"
      },
      {
        "name": "FlowRate",
        "dataType": "Float",
        "unit": "m3/h",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.FLOWRATE",
        "meaning": "Lu luong hoi luu"
      },
      {
        "name": "Pressure",
        "dataType": "Float",
        "unit": "bar",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.PRESSURE",
        "meaning": "Ap suat duong hoi luu"
      },
      {
        "name": "ChemicalDose",
        "dataType": "Float",
        "unit": "L",
        "tagType": "ANALOG",
        "tagCode": "CIP.SHD.CHEMICALDOSE",
        "meaning": "Luong hoa chat da bo sung"
      },
      {
        "name": "HeatingOn",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.HEATINGON",
        "meaning": "True khi may nuoi dang bat"
      },
      {
        "name": "CirculationOn",
        "dataType": "Boolean",
        "unit": null,
        "tagType": "DIGITAL",
        "tagCode": "CIP.SHD.CIRCULATIONON",
        "meaning": "True khi bom hoi luu dang chay"
      }
    ]
  }
];
