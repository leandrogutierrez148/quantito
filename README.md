# Quantito

**Quantito** is a serverless project for retrieving, processing, and analyzing financial data.

### Configuration (Environment Variables)

The pipeline is configured using environment variables:

| Variable | Description | Default Value |
| :--- | :--- | :--- |
| `EODHD_API_TOKEN` | Access token for the EODHD API (Required) | *None* |
| `SYMBOLS` | Comma-separated list of tickers to query | `AAPL.US,GOOGL.US` |

### Local Execution

To run the script directly with Python on your local machine:

```bash
# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment variables and run
export EODHD_API_TOKEN="your-token-here"
export SYMBOLS="AAPL.US,GOOGL.US"
python main.py
```

### Docker Execution

The project features a secure, optimized `Dockerfile` based on `python:3.11-slim` that runs processes with an unprivileged user.

```bash
# Build the image
docker build -t quantito-job .

# Run the container
docker run --env EODHD_API_TOKEN="your-token-here" quantito-job
```

### Deployment

For detailed information on the deployment architecture, configuration decisions, and the CI/CD pipeline on Google Cloud Platform (GCP), see [DEPLOYMENT.md](file:///Users/lgutierrez/Proyectos/quantito/DEPLOYMENT.md).

