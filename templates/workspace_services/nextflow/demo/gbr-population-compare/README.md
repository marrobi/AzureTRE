# British population comparison

A small demonstration pipeline for importing into an Azure TRE workspace through Airlock.

It takes a VCF annotated with 1000 Genomes allele frequencies, such as `variants/HG00096.annotated.vcf.gz` from a run of the **1000 Genomes British (GBR) germline demo**, and reports:

- how common the sample's variants are in British people (GBR, "British in England and Scotland");
- the variants that are rare in British people, or absent from 1000 Genomes;
- the variants whose British frequency differs most from the African, East Asian, South Asian and American groups.

**Outputs:** `report.html`, `rare_in_gbr.csv`, `differentiated.csv`, `multiqc_report.html` and `stats/`.

Tools run in the `staphb/bcftools`, `python` and `staphb/multiqc` images from Docker Hub, pulled through the TRE Nexus proxy.

This is a research demonstration, not a clinical test.
