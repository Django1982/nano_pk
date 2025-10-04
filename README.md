# nano_pk
Home Assistant integration of Hargassner Nano-PK pellet heating systems.

This is a custom component to integrate Hargassner heatings with Touch Tronic (touch screen control) into Home Assistant.
It will add a number of new sensors to your HA that display the current state of the heating.
All you need is a connection from your Hargassner heating directly from the Touch Tronic to your local LAN, the internet gateway is not required.
The nano_pk component does not allow remote control of your heating.

I have developed and tested it on a Nano-PK model, but chances are high it will work on other Hargassner models as well.
According to user reports, it is also compatible with Rennergy Mini PK heating models.
Read on how to try this and let me know if it works!

## Installation

### Via HACS (Recommended)
1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL and select category "Integration"
5. Click "Install" on the nano_pk integration
6. Restart Home Assistant

### Manual Installation
1. Create a folder `custom_components` in your Home Assistant `config` folder (if not yet done)
2. Copy all code from `custom_components/nano_pk` of this repository to `config/custom_components/nano_pk`
3. Restart Home Assistant

## Setup

### Setup via UI (Recommended)
**Version 0.3+ now includes a graphical configuration flow!**

1. After installation, go to **Settings → Devices & Services**
2. Click **+ Add Integration** and search for "Hargassner Nano-PK"
3. Follow the setup wizard:
   - Enter your boiler's **IP address** (shown on the Touch Tronic screen)
   - Provide a **device name** (default: "Hargassner")
   - Select **parameter set**: STANDARD (recommended) or FULL (all available sensors)
   - Choose **language**: English or German
4. Select your **message format template** or provide custom DAQPRJ XML:
   - **NANO_PK_FULL**: Pre-configured template with 97 channels (works for most Nano-PK models)
   - **Custom XML**: Paste your own DAQPRJ XML from SD card logging
5. Optionally upload **DE.CSV** for extended error code translations
6. Click **Submit** and your boiler will be added!

**Reconfiguration**: If you update your firmware or change network settings, use the **Reconfigure** option from the integration's menu.

### Legacy YAML Setup (Still Supported)
For backward compatibility, you can still configure via `configuration.yaml`:
```yaml
nano_pk:
  host: 192.168.0.10
  msgformat: NANO_V14L
  devicename: Nano-PK
  parameters: STANDARD
  language: DE
```

**Note**: YAML configurations will be automatically migrated to config entries on next restart.

## Configuration Parameters

### Required Parameters
- **host**: IP address of your heating (shown on the Touch Tronic screen after connecting to your local network)
- **msgformat**: Message format template or custom DAQPRJ XML
  - Built-in templates: `NANO_V14K`, `NANO_V14L`, `NANO_V14M`, `NANO_V14N`, `NANO_V14N2`, `NANO_V14O3`, `NANO_PK_FULL`
  - Custom XML: Paste DAQPRJ XML content from SD card

### Optional Parameters
- **devicename** (default: "Hargassner"): Name prefix for all heating sensors
- **parameters** (default: "STANDARD"): Sensor selection mode
  - `STANDARD`: Most important parameters (recommended for most users)
  - `FULL`: All available parameters from the heating
- **language** (default: "EN"): Language for boiler state sensor
  - `EN`: English
  - `DE`: German (Deutsch)

## Advanced Configuration

### Using Custom Message Formats
Different Hargassner models and firmware versions use different message formats. To use a custom format:

1. Enable **SD logging** on the Touch Tronic screen
2. Insert an SD card for a few seconds
3. Check the SD card on your computer for a file like `DAQ00000.DAQ`
4. Open this file in a text editor and find the XML section `<DAQPRJ> ... </DAQPRJ>` at the beginning
5. During setup, select **"Custom XML"** and paste the entire `<DAQPRJ>` section

### Extended Error Code Translations
For more detailed error descriptions, you can upload the DE.CSV file from your heating:

1. Obtain the **DE.CSV** file from your Touch Tronic's SD card or manufacturer
2. During setup (or reconfiguration), paste the CSV content when prompted
3. The integration will parse and use these extended error codes

See `custom_components/nano_pk/msgformats/README.md` for more details about message format templates.

## Features

### Sensors
The integration provides various sensors depending on your configuration:

**Standard Sensors** (STANDARD mode):
- Boiler operation status (error/OK)
- Boiler state (off, ignition, full firing, etc.)
- Boiler temperature
- Smoke gas temperature
- Output power
- Outside temperature
- Buffer temperatures (0-3)
- Return temperature
- Buffer fill level
- Pellet stock level
- Flow temperature
- Pellet consumption
- Energy consumption

**Full Mode** (FULL parameter set):
- All sensors from STANDARD mode
- Additional boiler-specific parameters (97+ channels total)

### Services
- **`nano_pk.get_diagnostics`**: Export diagnostic information to logs and `/config/nano_pk_diagnostics.json`
  - Integration configuration
  - Connection statistics
  - Entity states
  - Error code loading status

### Diagnostics Support
The integration includes comprehensive diagnostics:
- Connection health monitoring
- Reconnection statistics
- Error code translation status
- DE.CSV loading diagnostics
- Entity state tracking

## Troubleshooting

### Connection Issues
If the integration cannot connect to your boiler:
1. Verify the IP address shown on the Touch Tronic screen
2. Ensure your Home Assistant instance can reach the boiler's network
3. Check your firewall settings
4. Use the **Reconfigure** option to update the IP address

### Missing Sensors
If expected sensors are missing:
1. Check the logs for warnings about missing parameters
2. Try using **FULL** parameter mode to see all available sensors
3. Verify your message format template matches your boiler's firmware version
4. Use custom DAQPRJ XML if built-in templates don't work

### Extended Error Codes Not Loading
1. Run the `nano_pk.get_diagnostics` service to check DE.CSV status
2. Verify the DE.CSV file format (semicolon-separated, latin-1 encoding)
3. Check Home Assistant logs for parsing errors
4. Re-upload the DE.CSV via the **Reconfigure** option

## Compatibility

### Tested Models
- **Hargassner Nano-PK** (all firmware versions V14K - V14O3)
- **Rennergy Mini PK** (user-reported)

### Firmware Versions
This integration supports Touch Tronic firmware versions:
- V14K, V14L, V14M, V14N, V14N2, V14O3
- Custom firmware versions via DAQPRJ XML

**Note**: After firmware updates, use the **Reconfigure** option to update your message format if needed.

## Development

### Version History
- **v0.3**: Config flow UI, diagnostics, reconfiguration support, DE.CSV integration, improved error handling
- **v0.2**: Enhanced sensor support, better reconnection logic
- **v0.1**: Initial release with YAML configuration

### Contributors
- **@TheRealKillaruna**: Original integration development
- **@Django1982**: Config flow, diagnostics, UI improvements, and major refactoring

## Acknowledgements
[This code](https://github.com/Jahislove/Hargassner) by @Jahislove was very helpful to understand the messages sent by the heating - thank you!

## Feedback & Support
You can leave feedback for this custom component in the [corresponding thread](https://community.home-assistant.io/t/hargassner-heating-integration/288568) at the Home Assistant community forum.

For bug reports and feature requests, please use the [GitHub Issues](https://github.com/TheRealKillaruna/nano_pk/issues) page.
