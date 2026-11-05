# 1000 Genomes British (GBR) germline demo

A small germline short-variant pipeline on public UK-relevant data. It runs in about 15 minutes on the task pool.

- **Sample:** HG00096, a British (GBR, "British in England and Scotland") participant in the 1000 Genomes Project.
- **Reads:** 30x Illumina reads from the 1000 Genomes high-coverage release (New York Genome Center), for chr22:41.6–42.6 Mb on GRCh38. The region includes **CYP2D6**, a pharmacogene that affects the metabolism of about a quarter of prescribed medicines.
- **Steps:** FastQC, BWA-MEM alignment to GRCh38 chr22, duplicate marking with samtools, calling with bcftools, annotation with allele frequencies for British people and the five continental groups, and a comparison with the 1000 Genomes calls for HG00096.
- **Outputs:** `report.html` (population frequencies and CYP2D6 calls), `multiqc_report.html` (QC), `cyp2d6_variants.csv`, the annotated VCF and the BAM.

Tools run in [StaPH-B](https://staphb.org/docker-builds/) images from Docker Hub, pulled through the TRE Nexus proxy.

To call your own reads, upload paired FASTQ files on the **Data** page and select them as read 1 and read 2. They must be aligned to GRCh38 chr22 in the selected region.

This is a research demonstration, not a clinical test. CYP2D6 has a close pseudogene (CYP2D7) and structural variants that short reads cannot resolve, so the calls cannot be used to assign star alleles.

The image build prepares the bundled data with `prepare-demo-data.sh`. 1000 Genomes data is freely available without restriction; see the [1000 Genomes data reuse statement](https://www.internationalgenome.org/IGSR_disclaimer).
