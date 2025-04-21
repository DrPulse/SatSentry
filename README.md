# SatSentry

A comprehensive software solution that provides real-time tracking of Bitcoin addresses and extended public keys (xpub/ypub/zpub) for incoming and outgoing transactions. The software notifies users via Discord webhooks when it detects transactions for any monitored address.

## Features

- Monitor individual Bitcoin addresses for transactions
- Monitor addresses derived from extended public keys (xpub/ypub/zpub)
- Support for both public mempool.space API and self-hosted mempool instances
- Receive detailed Discord notifications for transactions
- Configure check intervals

## Installation

```bash
    git clone https://github.com/DrPulse/satsentry.git
    cd sat-sentry
```

### Using uv

```bash
uv sync
uv run satsentry
```

### Using python

```bash
pip install -r requirements.txt
python3 main.py
```

### Using Docker

1. Build the Docker image:

    ```bash
    docker build -t satsentry .
    ```

2. Run the Docker container:

    ```bash
    docker run -p 5000:5000 satsentry
    ```

Access the web interface at <http://localhost:5000>

## Configuration

### Settings

- **Check Interval**: How often to check for new transactions (in seconds)
- **Mempool API**: Choose between public mempool.space API or self-hosted instance
- **Discord Webhook**: URL for receiving notifications
- **Gap Limit**: Number of unused addresses to derive from extended public keys

### Adding Addresses

- Individual addresses can be added with optional labels
- Extended public keys (xpub/ypub/zpub) can be added with custom derivation paths

## Development

```bash
uv sync
uv run satsentry
```

### Running Tests

```bash
pytest
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

MIT
