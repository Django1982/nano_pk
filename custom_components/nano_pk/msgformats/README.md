# Message Format Templates

This directory contains DAQPRJ XML templates for different Hargassner boiler models.

## What is DAQPRJ?

The DAQPRJ XML format defines the structure of telnet messages from Hargassner boilers. Each boiler model may have a different channel configuration.

## How to use

### During Config Flow Setup:

1. **Select a template** - If your boiler model is listed, select it
2. **Custom XML** - If your model isn't listed, paste your custom DAQPRJ XML

### Getting your DAQPRJ XML:

You need to export the DAQPRJ XML from your Hargassner boiler's web interface or configuration tool. The exact location varies by model.

## Available Templates

### NANO_PK_FULL.xml
- **Model**: Hargassner Nano-PK (Full configuration)
- **Channels**: 97 analog + digital channels
- **Includes**:
  - Boiler temperatures (TK, TRL, TRG, etc.)
  - Oxygen sensor (O2)
  - Power output (Leistung)
  - Multiple heating circuits (HK A, 1, 2, B)
  - Buffer management (Puffer)
  - Hot water (FW)
  - Lambda sensor diagnostics
  - External heating circuits
  - Digital status bits

## XML Structure

```xml
<DAQPRJ>
  <ANALOG>
    <CHANNEL id='0' name='ZK' dop='0'/>
    <CHANNEL id='1' name='O2' unit='%'/>
    ...
  </ANALOG>
  <DIGITAL>
    <CHANNEL id='0' bit='0' name='Störung'/>
    ...
  </DIGITAL>
</DAQPRJ>
```

### Attributes:
- `id` - Channel ID (position in telnet message)
- `name` - Sensor/value name
- `unit` - Measurement unit (optional)
- `dop` - Decimal places (optional, default: 1)
- `bit` - Bit position for digital channels

## Telnet Message Format

The boiler sends messages via telnet (port 23) in this format:

```
pm [value0] [value1] [value2] ...
```

The DAQPRJ XML maps each position to a channel name and unit.

## DE.CSV Error Codes

In addition to DAQPRJ, you also need the DE.CSV file from your boiler for extended error code translations. This file is handled separately during config flow setup.
