#!/usr/bin/env bash
# Builds the demo data for the uk-1kg-germline pipeline from public 1000 Genomes and UCSC files.
# The runtime image build runs each step in a container with the tools it needs (see app/Dockerfile).
#   fetch   (needs curl)     chr22 reference and the 1000 Genomes population table
#   reads   (needs samtools) HG00096 read pairs over the demo region from the NYGC 30x CRAM
#   vcf     (needs bcftools) HG00096 truth calls and per-population allele frequencies
set -o errexit -o nounset -o pipefail

REGION="chr22:41600000-42600000"   # GRCh38, around CYP2D6 (chr22:42,126,499-42,130,865)
SAMPLE="HG00096"                   # British (GBR) sample in 1000 Genomes
KG="http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/1000G_2504_high_coverage"
CRAM="http://ftp.sra.ebi.ac.uk/vol1/run/ERR324/ERR3240114/${SAMPLE}.final.cram"
PANEL="${KG}/working/20220422_3202_phased_SNV_INDEL_SV/1kGP_high_coverage_Illumina.chr22.filtered.SNV_INDEL_SV_phased_panel.vcf.gz"
POPULATIONS="${KG}/20130606_g1k_3202_samples_ped_population.txt"
# UCSC hg38 chr22 has the same sequence as the GRCh38 analysis set used for the CRAM (soft-masked).
CHR22="https://hgdownload.soe.ucsc.edu/goldenPath/hg38/chromosomes/chr22.fa.gz"

out="${2:-/data}"
mkdir -p "${out}"
cd "${out}"

case "${1:?step: fetch, reads or vcf}" in
  fetch)
    curl -fsSL -o chr22.plain.fa.gz "${CHR22}"
    # Each sample belongs to its population (for example GBR) and its continental group (for example EUR).
    curl -fsSL "${POPULATIONS}" | awk 'NR > 1 { print $2 "\t" $6 "," $7 }' > sample_groups.tsv
    ;;
  reads)
    gzip -dc chr22.plain.fa.gz > chr22.fa
    samtools faidx chr22.fa
    samtools view -@ 4 -T chr22.fa -b -X -o region.bam "${CRAM}" "${CRAM}.crai" "${REGION}"
    samtools collate -@ 4 -u -O region.bam \
      | samtools fastq -@ 4 -n -1 "${SAMPLE}_R1.fastq.gz" -2 "${SAMPLE}_R2.fastq.gz" -0 /dev/null -s /dev/null -
    rm -f region.bam chr22.fa chr22.fa.fai
    ;;
  vcf)
    gzip -dc chr22.plain.fa.gz | bgzip -@ 4 > chr22.fa.gz
    bcftools view -r "${REGION}" -Ob -o panel.bcf "${PANEL}"
    bcftools view -s "${SAMPLE}" -c 1 panel.bcf \
      | bcftools annotate -x INFO -Oz -o "${SAMPLE}_1kg_truth.vcf.gz"
    bcftools +fill-tags panel.bcf -- -S sample_groups.tsv -t AF \
      | bcftools view -G \
      | bcftools annotate -x '^INFO/AF_GBR,INFO/AF_EUR,INFO/AF_AFR,INFO/AF_EAS,INFO/AF_SAS,INFO/AF_AMR' \
        -Oz -o 1kg_population_af.vcf.gz
    tabix -p vcf "${SAMPLE}_1kg_truth.vcf.gz"
    tabix -p vcf 1kg_population_af.vcf.gz
    rm -f panel.bcf
    ;;
  *)
    echo "Unknown step: $1" >&2
    exit 2
    ;;
esac
