# TRE demo pipeline

A small Nextflow pipeline for checking the Nextflow workspace service end to end.

1. `SIMULATE` runs one Azure Batch task per sample and writes a random walk to CSV.
2. `SUMMARISE` combines the samples and publishes `summary.csv`, `trajectories.svg`, `report.html` and `README.md`.

Both processes use the `python:3.12-bookworm` image from Docker Hub, which the Batch nodes pull through the TRE Nexus proxy. Slim images such as `python:3.12-slim` fail, because they lack the `ps` command that Nextflow needs to collect task metrics.

To use your own sample names, upload a text file with one name per line on the **Data** page and select it as the sample list.
