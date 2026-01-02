# HTTP-Service (v0.6)

This directory implements the HTTP-service feature for version 0.6.

## Planned Functionalities:

- Expose CLI-like behavior over HTTP
- Support queries from Expert Advisors
- MT4/MT5 compatibility
- Additional features to be added iteratively for seamless integration
- Metrics endpoint running in a separate thread
- Health endpoint running in a separate thread
- Basic HTML support for dashboards or minimal personalization
- Only listens on 127.0.0.1 (localhost)
- CORS * support is disabled for security
- Configuration via central YAML config
- Design and API specification will be published
- README.md to be split into docs/architecture.md and additional docs to reduce file size

## Configuration

A block in the ```config.user.yaml``` need to get added

```yaml
## Below you will find the configuration for the http service script.
http-service:
  docs: config/dukascopy/http-docs    # Directory where HTML docs will live
  listen: ":8000"                     # Listen to this port
  limits:
    max_page: 1000                    # Maximum number of pages to support
    max_per_page: 1000                # Maximum number of rows per page
```

## URI definition

While not necessarily optimal, this approach provides full compatibility with the builder’s select options. By mirroring the builder syntax exactly, the API remains intuitive and easy to learn: if you know the builder syntax, you already know the URI syntax, and vice versa.

```sh
# http://localhost:8000/ohlcv/1.0/select/SYMBOL:test,TF1,TF2:skiplast:test/ \
# select/SYMBOL,TF1/after/2025-01-01+00:00:00/output/CSV/MT4?page=1&order=asc&limit=1000
```

Outputs can be:

- JSON \
  Simple JSON records
- JSONP \
  Simple JSON records wrapped with a callback method
- CSV \
  Pure CSV text

## Output formats 

Will be posted here soon.

## ETA

This will be done very soon. This is easy stuff compared to the rest.