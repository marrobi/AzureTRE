#!/usr/bin/env nextflow
/*
 * Compares a sample's variant calls with British (GBR) and global 1000 Genomes allele frequencies.
 * Input: a VCF annotated with INFO/AF_GBR, AF_EUR, AF_AFR, AF_EAS, AF_SAS and AF_AMR, such as
 * variants/<sample>.annotated.vcf.gz from the "1000 Genomes British (GBR) germline demo" pipeline.
 * Research demonstration only.
 */

params.vcf     = null
params.max_af  = 0.01
params.top_n   = 15
params.outdir  = 'results'

process EXTRACT {
    tag "${vcf.simpleName}"
    container 'staphb/bcftools:1.24'
    cpus 1
    memory '1 GB'
    publishDir "${params.outdir}/stats", mode: 'copy', pattern: '*.bcftools_stats.txt'

    input:
    path vcf

    output:
    path 'variants.tsv', emit: table
    path '*.bcftools_stats.txt', emit: stats

    script:
    """
    for tag in AF_GBR AF_EUR AF_AFR AF_EAS AF_SAS AF_AMR; do
        bcftools view -h ${vcf} | grep -q "ID=\${tag}," || {
            echo "The VCF has no INFO/\${tag}. Use an annotated VCF from the germline demo pipeline." >&2
            exit 1
        }
    done
    bcftools view -f PASS,. ${vcf} \\
        | bcftools query -f '%CHROM\\t%POS\\t%REF\\t%ALT\\t%QUAL\\t[%GT]\\t%INFO/AF_GBR\\t%INFO/AF_EUR\\t%INFO/AF_AFR\\t%INFO/AF_EAS\\t%INFO/AF_SAS\\t%INFO/AF_AMR\\n' \\
        > variants.tsv
    bcftools stats ${vcf} > ${vcf.simpleName}.bcftools_stats.txt
    """
}

process REPORT {
    container 'python:3.12-bookworm'
    cpus 1
    memory '1 GB'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path table
    path report_script

    output:
    path 'report.html'
    path 'rare_in_gbr.csv'
    path 'differentiated.csv'

    script:
    """
    python3 ${report_script} --table ${table} --max-af ${params.max_af} --top ${params.top_n} --title '${params.vcf.tokenize('/').last()}'
    """
}

process MULTIQC {
    container 'staphb/multiqc:1.35'
    cpus 1
    memory '2 GB'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path stats

    output:
    path 'multiqc_report.html'

    script:
    """
    multiqc --title 'British population comparison' --filename multiqc_report.html --no-ai --force .
    """
}

workflow {
    if (!params.vcf) {
        error "Choose an annotated VCF, for example variants/HG00096.annotated.vcf.gz from a germline demo run."
    }
    vcf = file(params.vcf, checkIfExists: true)
    EXTRACT(vcf)
    REPORT(EXTRACT.out.table, file("${projectDir}/assets/report.py", checkIfExists: true))
    MULTIQC(EXTRACT.out.stats)
}
