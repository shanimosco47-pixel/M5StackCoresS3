# Local serial capture

`capture_serial.py` is the utility used during the device diagnosis.
Install pyserial in a local Python environment (`python -m pip install pyserial`).
It can also use a neighboring local `pydeps` directory. No credentials are embedded.

```sh
python capture_serial.py --port YOUR_SERIAL_PORT --seconds 30 --output private-capture.log
```

The script avoids a serial reset and refuses to overwrite an existing capture.
It redacts the old firmware's known password/key labels and OpenAI key patterns,
but does not promise to redact every provider or every kind of personal data.
Treat every capture as private and inspect locally. Do not publish raw logs.
Port names vary by device and host; the script's historical default is not a current-device guarantee.
