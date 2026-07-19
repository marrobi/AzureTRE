# Locking and enforcing template parameters

When you author a workspace, workspace service, shared service, or user resource template, every property you declare in `template_schema.json` becomes an input field that the person deploying the resource (a TRE Admin or Workspace Owner) can fill in through the TRE portal or the API.

Sometimes that is exactly what you want. In other cases the template author has made a deliberate decision — for example "this workspace **always** deploys Guacamole and Azure ML" — and you do **not** want the person deploying the resource to be able to override it.

This page explains how a parameter flows through TRE, which mechanisms let you lock or constrain a value, how strongly each one is enforced, and whether the value needs to be passed through Porter.

!!! tip
    If instead of locking an individual property you want to restrict *which workspace service templates* can be deployed into a workspace, see [Restricting which workspace service templates can be deployed](./authoring-workspace-templates.md#restricting-which-workspace-service-templates-can-be-deployed).

## How a parameter flows through TRE

Understanding the flow makes it clear where a value can be enforced and where it is merely a display hint.

1. **`template_schema.json`** declares a property. This is a standard [JSON Schema](http://json-schema.org/) document. The API and the portal use it to build the deployment form and to validate what is submitted.
2. **The portal** renders the schema as a form using [`react-jsonschema-form`](https://rjsf-team.github.io/react-jsonschema-form/). The value the user supplies is sent to the API.
3. **The API** validates the submitted properties against the (enriched) template schema with a JSON Schema validator on **both create and update**. Anything that violates the schema is rejected before the resource is persisted. The accepted properties are stored on the resource document in Cosmos DB.
4. **The resource processor** builds the `porter` command. It asks Porter which parameters the bundle declares (`porter explain`) and, for each one, looks up a value — first in the resource's `properties`. A property is therefore only handed to the bundle (and to your Terraform) if `porter.yaml` declares a **matching parameter**.

The important consequence: **schema validation is server-side and authoritative**, whereas some presentation hints (see `readOnly` below) are applied only by the portal.

## Does the value need to be passed through Porter?

Only if the bundle needs to act on it.

* If your Terraform (or other install logic) uses the value — for example a `deploy_azureml` flag that decides whether to create the Azure ML resources — then `porter.yaml` **must** declare a matching parameter so the resource processor passes the value through. This is true regardless of whether the value is locked: a `const` value is still passed to Porter, it simply cannot be changed.
* If the value is only used by the API for validation or metadata and never influences the deployment — for example the `allowed_workspace_service_templates` restriction, which the API enforces itself — then it does **not** need to be a Porter parameter. It is stored and validated without ever reaching the bundle.

In short: declare a Porter parameter when the bundle consumes the value; you do not need one purely to display or validate a value. Whether the property is editable or locked does not change this rule.

## Mechanisms for constraining a value

| Mechanism | Where declared | Enforced by | Effect |
| --------- | -------------- | ----------- | ------ |
| `const` | `template_schema.json` property | API (server-side) **and** portal | Pins the property to exactly one allowed value. The field is still shown in the portal, but any other value is rejected on create and update. |
| `enum` | `template_schema.json` property | API (server-side) **and** portal | Restricts the value to a fixed list of choices. |
| `default` | `template_schema.json` property | Portal (pre-fill) | Pre-populates the field. On its own it does **not** prevent a different value being submitted. |
| `updateable: false` | `template_schema.json` property | API (server-side) | The value can be set at create time but cannot be changed on a later update. On update the API marks the property `readOnly`. |
| Hardcode in `porter.yaml` / Terraform | Bundle | Bundle | The value is fixed inside the bundle and never surfaced as a form field. Strongest, but not visible in the portal. |
| `readOnly: true` | `template_schema.json` property | **Portal only** | The portal renders the field as read-only and strips it before submitting. **Not** a server-side constraint — a value sent directly to the API is not rejected. Do not rely on it as a security boundary. |
| `authorizedRoles` | `template_schema.json` (template level) | API (server-side) | Controls *who* may deploy the template, not the value of individual fields. |

### Recommended approach: `const`

For the common case — "show the value in the TRE portal, but do not let the person deploying it override the template author's decision" — use `const`.

* It keeps the property **visible** in the portal (unlike hardcoding it in the bundle, which would hide it and typically only expose it as an output).
* It is **enforced server-side**: the API's JSON Schema validation rejects any other value on both create and update, so it cannot be bypassed by calling the API directly. This is unlike `readOnly`, which JSON Schema treats as an annotation rather than a constraint and which the portal alone honours.

There is already precedent for a top-level `const` in the repository: the Sonatype Nexus shared service pins `accept_nexus_eula` to `true` in its `template_schema.json`.

## Example: force Azure ML and Guacamole to be deployed

The following `template_schema.json` fragment declares two toggles that are shown in the portal but locked to `true`, so the person deploying the workspace can see that these services will be provisioned but cannot turn them off. Set `default` equal to the `const` value so the field is pre-satisfied.

```json
{
  "properties": {
    "deploy_azureml": {
      "type": "boolean",
      "title": "Deploy Azure Machine Learning",
      "description": "Azure ML is always deployed with this workspace and cannot be disabled.",
      "default": true,
      "const": true
    },
    "deploy_guacamole": {
      "type": "boolean",
      "title": "Deploy Apache Guacamole",
      "description": "Guacamole is always deployed with this workspace and cannot be disabled.",
      "default": true,
      "const": true
    }
  }
}
```

If the bundle acts on these values, declare matching parameters in `porter.yaml` so the resource processor passes them to your install logic:

```yaml
parameters:
  - name: deploy_azureml
    type: boolean
    default: true
  - name: deploy_guacamole
    type: boolean
    default: true
```

Your Terraform then reads the parameters as it would any other input. Because the schema locks the values with `const`, they will always arrive as `true`.

### Allowing a value to be set once, then locked

If you want the person deploying the resource to **choose** a value at create time but not change it afterwards, use `updateable: false` instead of `const`. A property is settable at create time regardless of `updateable`; the flag only controls whether it can be changed on a later update.

* `const` — the author fixes the value; the deployer can never change it.
* `updateable: false` — the deployer picks the value at create time; it is then locked.
* `updateable: true` — the deployer can change the value later. If `updateable` is omitted it defaults to `false`, so the value is settable at create time and then locked (equivalent to `updateable: false`).

## Summary

* Every `template_schema.json` property is an editable form field by default.
* To lock a value while keeping it visible in the portal, use `const` — it is enforced server-side on create and update.
* Use `enum` to constrain to a fixed set of choices, and `updateable: false` to allow a value to be set once and then locked.
* Avoid relying on `readOnly` to enforce intent: it is applied by the portal only and does not prevent a direct API call from supplying another value.
* A property only needs a matching `porter.yaml` parameter if the bundle acts on the value; API-only constraints do not need to be passed through Porter.
