# Build / ops › Operations › Prometheus
enforcer · A monitoring system. Its `promtool` checks Prometheus rule and configuration files.

- no recipe: Prometheus (its tarball has promtool)
- check: `promtool check rules <file>`

From the leaf's note:

Install: `wget -qO- https://github.com/prometheus/prometheus/releases/download/v3.15.0/prometheus-3.15.0.linux-amd64.tar.gz | tar -xz -C /opt/enforce`.
Use: `/opt/enforce/prometheus-3.15.0.linux-amd64/promtool check rules <file>`.

Docs: https://prometheus.io/docs/prometheus/latest/command-line/promtool/
