#!/usr/bin/env nextflow

params.input = null
params.samples = 4
params.steps = 50
params.title = 'Azure TRE Nextflow demo'
params.outdir = 'results'

process SIMULATE {
    tag "${sample}"
    container 'python:3.12-bookworm'
    cpus 1
    memory '1 GB'

    input:
    val sample

    output:
    path "${sample}.csv"

    script:
    template 'simulate.py'
}

process SUMMARISE {
    container 'python:3.12-bookworm'
    cpus 1
    memory '1 GB'
    publishDir params.outdir, mode: 'copy'

    input:
    path csvs

    output:
    path 'summary.csv'
    path 'trajectories.svg'
    path 'report.html'
    path 'README.md'
    path 'samples', type: 'dir'

    script:
    title_json = groovy.json.JsonOutput.toJson(params.title as String)
    template 'summarise.py'
}

workflow {
    samples = params.input
        ? channel.fromPath(params.input, checkIfExists: true)
            .splitText()
            .map { line -> line.trim() }
            .filter { name -> name ==~ /[A-Za-z0-9_.-]{1,64}/ }
        : channel.of(1..(params.samples as int)).map { n -> "sample_${n}" }

    SIMULATE(samples)
    SUMMARISE(SIMULATE.out.collect())
}
