# Demo: bring a Nextflow pipeline in through Airlock and run it

This script shows a researcher importing their own Nextflow pipeline into a secure workspace through Airlock, adding it to the workspace's Nextflow service from a workspace VM, and running it on results from an earlier run.
It runs in parts, so you can stop after any part or show only some of them.

| Part | What it shows | Time |
| --- | --- | --- |
| [1. Request the import](#part-1-request-the-import) | A researcher brings code in through an Airlock import request | 5 min |
| [2. Approve the import](#part-2-approve-the-import) | An Airlock Manager reviews and approves it | 3 min |
| [3. Get the pipeline into the workspace](#part-3-get-the-pipeline-into-the-workspace) | The approved file is only reachable from inside the workspace | 5 min |
| [4. Add and launch the pipeline](#part-4-add-and-launch-the-pipeline) | Importing the zip into the Nextflow portal and launching it on an earlier run's results | 5 min, then 10–15 min of run time |
| [5. Explore the results](#part-5-explore-the-results) | Reports, tables and Nextflow's own reports, all inside the workspace | 5 min |
| [6. Optional extras](#part-6-optional-extras) | Airlock export of a result, and Azure Databricks in the same workspace | 5 min each |

The demo pipeline is [gbr-population-compare](gbr-population-compare/README.md).
It takes the annotated VCF from the built-in **1000 Genomes British (GBR) germline demo** and reports which of the sample's variants are rare in British people, and which differ most from other populations.
It uses only public 1000 Genomes data.

## Before the demo

Do these steps the day before, and check them again 30 minutes before you start.

1. In a terminal with this repository, create the zip that you'll import:

   ```bash
   templates/workspace_services/nextflow/demo/make-pipeline-zip.sh ~/gbr-population-compare.zip
   ```

1. Check that the presenter's account has the roles that the demo needs in the workspace:
   - **Workspace Owner** or **Workspace Researcher**, to create the request and use the VM and the Nextflow portal.
   - **Airlock Manager**, to approve the request. In a real TRE a different person approves requests. Say so when you approve.

1. In the TRE UI, open the workspace and check:
   - **Virtual Desktops** (Guacamole) has a running Windows VM. If it's stopped, select **Actions** > **Start**. It takes about 3 minutes.
   - **Nextflow** is deployed. Copy its connection URL for Part 3.
   - The Nextflow portal has a finished **1000 Genomes British (GBR) germline demo** run. If not, launch one with the default parameters. It takes about 20 minutes.

1. Optionally, run the imported pipeline once in advance, then delete it from **Data** > **Pipelines** so that the live import in Part 4 is a fresh one.
   The earlier run stays on **Runs**, which gives you finished results to show in Part 5 while the live run is still going.

1. About 15 minutes before Part 4, launch the built-in **TRE demo** pipeline. Batch pools scale from zero and take 5–10 minutes to start their first node, so this keeps a node ready for the live run.

1. Open these tabs on the presenter's computer: the TRE UI on the workspace's **Airlock** page, and a terminal in the folder with the zip.

## Part 1: Request the import

**Story:** "I've written a small analysis pipeline outside the TRE. The workspace has no internet access, so the only way to bring code or data in is an Airlock request that someone has to approve."

1. In the TRE UI, open the workspace and select **Airlock** > **New request** > **Import**.
1. Enter a title, such as `gbr-population-compare pipeline`, and a justification, such as `Nextflow pipeline code for comparing variant calls with British allele frequencies. Code only, no data.` Select **Create**.
1. In **Files**, select **Generate** and copy the URL. It's a short-lived SAS URL for this request's container.
1. Upload the zip. Airlock takes one file per request, which is why the pipeline is zipped.

   ```bash
   SAS_URL='<paste the URL>'
   az storage blob upload --file gbr-population-compare.zip --blob-url "${SAS_URL%%\?*}/gbr-population-compare.zip?${SAS_URL#*\?}"
   ```

   You can also use Azure Storage Explorer: **Connect** > **Blob container** > **Shared access signature URL**.
1. Select **Submit**. The status changes to **Submitted**, then **In review** after the Airlock processor has checked the file, which takes about a minute.

**Point out:** the request records who brought what in, and why. If malware scanning is turned on, the file is scanned before review.

## Part 2: Approve the import

**Story:** "A data steward, here the workspace's Airlock Manager, decides what comes in."

1. On **Airlock**, open the request and select **Review**.
1. Optionally, show that an Airlock Manager can create a review VM to inspect the file in isolation.
1. Select **Approve**, add a note such as `Pipeline code reviewed: bcftools, Python and MultiQC from Docker Hub. No data.`, and submit.
1. The status changes to **Approval in progress**, then **Approved** within about a minute.

**Point out:** the decision and the note stay with the request. A rejected file is deleted and never reaches the workspace.

## Part 3: Get the pipeline into the workspace

**Story:** "The approved file is now in storage that only the workspace can reach."

1. On the approved request, select **Generate** in **Files** and copy the URL.
1. Optionally, paste the URL into a browser on your own computer and show that it doesn't download. The storage is only reachable through the workspace's private endpoint.
1. Go to the workspace's **Virtual Desktops** service and connect to the Windows VM.
1. In the VM, open Edge and paste the URL, adding `/gbr-population-compare.zip` before the `?`. Edge saves the zip to **Downloads**.
   To paste into the VM, use the Guacamole clipboard: press <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>, paste into the clipboard box, then close the panel and paste in the VM.
   Copying out of the VM is turned off, so nothing leaves the workspace this way.
1. In Edge, open the Nextflow service's connection URL and sign in with your TRE account.

**Point out:** the Nextflow portal has no public endpoint. It only works from inside the workspace, and it uses the workspace's own sign-in and roles.

## Part 4: Add and launch the pipeline

**Story:** "Now I add my pipeline to the workspace's Nextflow service and run it on results that an earlier pipeline produced, without moving any data out."

1. On **Pipelines**, select **Import pipeline (.zip)** and choose `Downloads\gbr-population-compare.zip`.
   The portal shows **Imported gbr-population-compare (4 files)**, and a **British population comparison** card appears.
1. Optionally, show that the portal rejects a zip with unsafe paths, and asks before replacing a pipeline of the same name.
1. On the card, select **Launch**.
   The launch form comes from the pipeline's `nextflow_schema.json`, the same format that nf-core pipelines use.
1. Enter a **Run label**, such as `HG00096 vs British frequencies`.
1. For **Annotated VCF**, select **Browse**, then **Results**.
   Run folders show the run's label and pipeline. Open the germline demo run, then `variants`, and select `HG00096.annotated.vcf.gz`.
   The browser only shows files that match the parameter's `pattern`, so only annotated VCFs appear. Turn on **Show all files** to show the rest.
1. Leave the other parameters at their defaults and select **Start run**.
1. On the run's **Overview**, show the run moving from **Queued** to **Running**, and the tasks appearing as Nextflow submits them to the workspace's private Azure Batch pools.

**Point out:**

- Each task runs in a container on Batch nodes inside the workspace network. The nodes have no public IP addresses and can only pull images through the TRE's Nexus proxy.
- Inputs, intermediate files and results stay in the workspace storage account.
- Nobody installed Nextflow, Java or Docker on the VM. The VM only needs a browser.

## Part 5: Explore the results

If the live run is still going, open the run that you made before the demo.

1. On the run's **Results** tab, **Key outputs** lists `report.html` first. Open it:
   - the British allele frequency of the sample's variants;
   - the variants that are rare in British people, or absent from 1000 Genomes;
   - the variants whose British frequency differs most from the African, East Asian, South Asian and American groups.
1. Open `rare_in_gbr.csv` to show the table preview, and `multiqc_report.html`.
1. On **Reports**, show Nextflow's timeline and execution report, with each task's CPU, memory and duration.
1. On **Data** > **Results**, show that every run's outputs are kept by run, and can be used as inputs to the next run.

## Part 6: Optional extras

### Export a result through Airlock

1. In the VM, download `rare_in_gbr.csv` from the run's **Results** tab.
1. In the TRE UI, create an **Export** request, generate its URL, and upload the file from the VM with the URL as in Part 1.
1. Submit the request and approve it as in Part 2. Then generate the download URL on your own computer and download the file.

**Point out:** results can only leave the workspace after review, the same way data comes in.

### Azure Databricks

If the workspace has the **Azure Databricks** service, open its connection URL from the VM.
It runs in the same workspace network as Nextflow, so a researcher can analyse pipeline results with Spark without them leaving the workspace.

## After the demo

- On the Nextflow portal's **Data** > **Pipelines**, delete the `gbr-population-compare` folder if you want to run Part 4 again.
- Stop the Windows VM from the TRE UI. The Batch pools scale back to zero by themselves.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Creating the Airlock request fails with **Failed to fetch workspace role assignments** (503) | An account has a default access assignment on the workspace application, which user consent creates. API 0.28.10 ignores it. On older versions, remove the assignment in Entra ID: **Enterprise applications** > the workspace application > **Users and groups**, and remove the entry with the role **Default Access**. |
| The upload in Part 1 fails with **AuthorizationFailure** (403) | The Airlock import storage account (`stalairlock<tre_id>`) doesn't allow public network access. TRE deploys it with public access, but an Azure Policy can turn it off. Ask for a policy exemption for that account, or upload from a network with a private endpoint to it. |
| The run stays **Queued** for more than 10 minutes | The Batch pools scale up every 5 minutes. Check the head pool's nodes in the Azure portal, and the Batch account's core quota for the VM family. |
| A task fails to pull its image | Check the TRE Nexus proxy and the workspace firewall rules. Only Docker Hub images are proxied. |
| **Annotated VCF** shows no files | No germline demo run has finished yet. Turn on **Show all files**, or run the germline demo first. |
