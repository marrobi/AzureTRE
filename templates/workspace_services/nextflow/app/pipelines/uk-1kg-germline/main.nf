#!/usr/bin/env nextflow
/*
 * Germline short-variant calling for a British (GBR) 1000 Genomes sample, annotated with
 * British and global allele frequencies and checked against the 1000 Genomes calls.
 * Research demonstration only: short reads cannot resolve CYP2D6 star alleles reliably.
 */

params.sample         = 'HG00096'
params.reads_1        = "${projectDir}/data/HG00096_R1.fastq.gz"
params.reads_2        = "${projectDir}/data/HG00096_R2.fastq.gz"
params.reference      = "${projectDir}/data/chr22.fa.gz"
params.truth          = "${projectDir}/data/HG00096_1kg_truth.vcf.gz"
params.population_af  = "${projectDir}/data/1kg_population_af.vcf.gz"
params.region         = 'chr22:41600000-42600000'
params.min_qual       = 30
params.outdir         = 'results'

process FASTQC {
    tag "${sample}"
    container 'staphb/fastqc:0.12.1'
    cpus 2
    memory '2 GB'
    publishDir "${params.outdir}/qc/fastqc", mode: 'copy'

    input:
    tuple val(sample), path(reads_1), path(reads_2)

    output:
    path '*_fastqc.zip', emit: zip
    path '*_fastqc.html'

    script:
    """
    fastqc --threads ${task.cpus} --quiet ${reads_1} ${reads_2}
    """
}

process PREPARE_REFERENCE {
    container 'staphb/samtools:1.24'
    cpus 1
    memory '2 GB'

    input:
    path reference

    output:
    tuple path(reference), path("${reference}.fai"), path("${reference}.gzi")

    script:
    """
    samtools faidx ${reference}
    """
}

process BWA_INDEX {
    container 'staphb/bwa:0.7.19'
    cpus 1
    memory '4 GB'

    input:
    path reference

    output:
    path 'bwa_index'

    script:
    """
    mkdir bwa_index
    bwa index -p bwa_index/reference ${reference}
    """
}

process BWA_MEM {
    tag "${sample}"
    container 'staphb/bwa:0.7.19'
    cpus 4
    memory '8 GB'

    input:
    tuple val(sample), path(reads_1), path(reads_2)
    path index

    output:
    tuple val(sample), path("${sample}.sam")

    script:
    """
    bwa mem -t ${task.cpus} -R '@RG\\tID:${sample}\\tSM:${sample}\\tPL:ILLUMINA' \\
        ${index}/reference ${reads_1} ${reads_2} > ${sample}.sam
    """
}

process MARK_DUPLICATES {
    tag "${sample}"
    container 'staphb/samtools:1.24'
    cpus 2
    memory '4 GB'
    publishDir "${params.outdir}/alignment", mode: 'copy', pattern: '*.{bam,bai}'
    publishDir "${params.outdir}/qc/samtools", mode: 'copy', pattern: '*.{stats,flagstat,txt}'

    input:
    tuple val(sample), path(sam)

    output:
    tuple val(sample), path("${sample}.bam"), path("${sample}.bam.bai"), emit: bam
    path "${sample}.stats", emit: stats
    path "${sample}.flagstat", emit: flagstat
    path "${sample}.markdup.txt", emit: markdup
    path "${sample}.depth.txt", emit: depth

    script:
    """
    samtools fixmate -@ ${task.cpus} -m ${sam} - \\
        | samtools sort -@ ${task.cpus} -m 1G - \\
        | samtools markdup -@ ${task.cpus} -f ${sample}.markdup.txt - ${sample}.bam
    samtools index ${sample}.bam
    samtools stats ${sample}.bam > ${sample}.stats
    samtools flagstat ${sample}.bam > ${sample}.flagstat
    samtools depth -a -r ${params.region} ${sample}.bam \\
        | awk '{ total += \$3; n += 1 } END { printf "%.1f\\n", (n ? total / n : 0) }' > ${sample}.depth.txt
    """
}

process CALL_VARIANTS {
    tag "${sample}"
    container 'staphb/bcftools:1.24'
    cpus 2
    memory '4 GB'

    input:
    tuple val(sample), path(bam), path(bai)
    tuple path(reference), path(fai), path(gzi)

    output:
    tuple val(sample), path("${sample}.calls.vcf.gz"), path("${sample}.calls.vcf.gz.tbi")

    script:
    """
    bcftools mpileup --threads ${task.cpus} -f ${reference} -r ${params.region} -a FORMAT/AD,FORMAT/DP -Ou ${bam} \\
        | bcftools call --threads ${task.cpus} -m -v -Ou \\
        | bcftools norm -f ${reference} -m -any -Ou \\
        | bcftools filter -e 'QUAL<${params.min_qual}' -s LowQual -Ou \\
        | bcftools sort -Oz -o ${sample}.calls.vcf.gz
    tabix -p vcf ${sample}.calls.vcf.gz
    """
}

process ANNOTATE {
    tag "${sample}"
    container 'staphb/bcftools:1.24'
    cpus 1
    memory '2 GB'
    publishDir "${params.outdir}/variants", mode: 'copy'

    input:
    tuple val(sample), path(vcf), path(tbi)
    tuple path(population_af), path(population_af_tbi)

    output:
    tuple val(sample), path("${sample}.annotated.vcf.gz"), path("${sample}.annotated.vcf.gz.tbi"), emit: vcf
    path "${sample}.bcftools_stats.txt", emit: stats

    script:
    """
    bcftools annotate -a ${population_af} \\
        -c INFO/AF_GBR,INFO/AF_EUR,INFO/AF_AFR,INFO/AF_EAS,INFO/AF_SAS,INFO/AF_AMR \\
        -Oz -o ${sample}.annotated.vcf.gz ${vcf}
    tabix -p vcf ${sample}.annotated.vcf.gz
    bcftools stats -s - ${sample}.annotated.vcf.gz > ${sample}.bcftools_stats.txt
    """
}

process EVALUATE {
    tag "${sample}"
    container 'staphb/bcftools:1.24'
    cpus 1
    memory '2 GB'
    publishDir "${params.outdir}/evaluation", mode: 'copy'

    input:
    tuple val(sample), path(vcf), path(tbi)
    tuple path(truth), path(truth_tbi)
    tuple path(reference), path(fai), path(gzi)

    output:
    path "${sample}_truth_comparison_mqc.tsv", emit: table

    script:
    """
    bcftools view -f PASS -Oz -o calls.pass.vcf.gz ${vcf} && tabix -p vcf calls.pass.vcf.gz
    # Left-aligning indels can move records, so sort before indexing.
    bcftools norm -f ${reference} -m -any -r ${params.region} -Ou ${truth} | bcftools sort -Oz -o truth.norm.vcf.gz
    tabix -p vcf truth.norm.vcf.gz
    printf '# id: truth_comparison\\n# section_name: "Comparison with 1000 Genomes calls"\\n# description: "PASS calls compared with the 1000 Genomes high-coverage calls for ${sample} in ${params.region}, matching position and alleles."\\n# format: tsv\\n# plot_type: table\\n' > ${sample}_truth_comparison_mqc.tsv
    printf 'Type\\tTrue positives\\tFalse positives\\tFalse negatives\\tPrecision\\tRecall\\tF1\\n' >> ${sample}_truth_comparison_mqc.tsv
    for type in snps indels; do
        rm -rf isec
        bcftools view -v \$type -Oz -o calls.\$type.vcf.gz calls.pass.vcf.gz && tabix -p vcf calls.\$type.vcf.gz
        bcftools view -v \$type -Oz -o truth.\$type.vcf.gz truth.norm.vcf.gz && tabix -p vcf truth.\$type.vcf.gz
        bcftools isec -c none -p isec calls.\$type.vcf.gz truth.\$type.vcf.gz
        fp=\$(grep -vc '^#' isec/0000.vcf || true)
        fn=\$(grep -vc '^#' isec/0001.vcf || true)
        tp=\$(grep -vc '^#' isec/0002.vcf || true)
        awk -v t=\$type -v tp=\$tp -v fp=\$fp -v fn=\$fn 'BEGIN {
            p = (tp + fp) ? tp / (tp + fp) : 0; r = (tp + fn) ? tp / (tp + fn) : 0; f = (p + r) ? 2 * p * r / (p + r) : 0
            printf "%s\\t%d\\t%d\\t%d\\t%.3f\\t%.3f\\t%.3f\\n", (t == "snps" ? "SNVs" : "Indels"), tp, fp, fn, p, r, f }' \\
            >> ${sample}_truth_comparison_mqc.tsv
    done
    """
}

process REPORT {
    tag "${sample}"
    container 'python:3.12-bookworm'
    cpus 1
    memory '1 GB'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(sample), path(vcf), path(tbi)
    path comparison
    path flagstat
    path depth

    output:
    path 'report.html'
    path 'cyp2d6_variants.csv'
    path 'README.md'

    script:
    template 'report.py'
}

process MULTIQC {
    container 'staphb/multiqc:1.35'
    cpus 1
    memory '2 GB'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path qc_files

    output:
    path 'multiqc_report.html'

    script:
    """
    multiqc --title '1000 Genomes British (GBR) germline demo' --filename multiqc_report.html --no-ai --force .
    """
}

workflow {
    reads = channel.of(tuple(params.sample, file(params.reads_1, checkIfExists: true), file(params.reads_2, checkIfExists: true)))
    reference = file(params.reference, checkIfExists: true)
    truth = tuple(file(params.truth, checkIfExists: true), file("${params.truth}.tbi", checkIfExists: true))
    population_af = tuple(file(params.population_af, checkIfExists: true), file("${params.population_af}.tbi", checkIfExists: true))

    FASTQC(reads)
    indexed_reference = PREPARE_REFERENCE(reference)
    BWA_MEM(reads, BWA_INDEX(reference))
    MARK_DUPLICATES(BWA_MEM.out)
    CALL_VARIANTS(MARK_DUPLICATES.out.bam, indexed_reference)
    ANNOTATE(CALL_VARIANTS.out, population_af)
    EVALUATE(CALL_VARIANTS.out, truth, indexed_reference)
    REPORT(ANNOTATE.out.vcf, EVALUATE.out.table, MARK_DUPLICATES.out.flagstat, MARK_DUPLICATES.out.depth)
    MULTIQC(FASTQC.out.zip.mix(MARK_DUPLICATES.out.stats, MARK_DUPLICATES.out.flagstat, ANNOTATE.out.stats, EVALUATE.out.table).collect())
}
