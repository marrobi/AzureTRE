# pgsc_calc: polygenic scores (PGS Catalog)

The [PGS Catalog Calculator](https://github.com/PGScatalog/pgsc_calc) (`pgsc_calc` v2.3.0) from the University of Cambridge and EMBL-EBI calculates polygenic scores for target genomes using scoring files from the [PGS Catalog](https://www.pgscatalog.org/).

The bundled example scores the CINECA synthetic genomes (chromosome 22) with [PGS001229](https://www.pgscatalog.org/score/PGS001229/), a standing height score trained on **UK Biobank** by the Global Biobank Engine. Results include the scores for each sample and an HTML report of variant matching.

To score your own data, bring genomes and PGS Catalog scoring files into the workspace through Airlock, upload a samplesheet on the **Data** page, and select it here.

How it runs in the TRE:

- The image contains the pipeline at the v2.3.0 tag and the `nf-schema` plugin it needs, because the workspace can't reach GitHub or the plugin registry.
- Its containers come from `ghcr.io/pgscatalog`, which Batch nodes can't reach. A TRE administrator copies them into the TRE container registry with `mirror-pipeline-images.sh`, and `tre.config` points the pipeline at those copies.
- Downloading scores by PGS ID, liftover chain files and ancestry reference panels needs internet access, so those options aren't offered in the launch form.

pgsc_calc is licensed under the Apache License 2.0.
