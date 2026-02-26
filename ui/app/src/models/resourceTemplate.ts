import { ResourceType } from "./resourceType";

export interface ResourceTemplate {
  id: string;
  name: string;
  type: string;
  description: string;
  version: string;
  title: string;
  resourceType: ResourceType;
  current: boolean;
  properties: any;
  allOf?: Array<any>;
  system_properties: any;
  actions: Array<TemplateAction>;
  customActions: Array<TemplateAction>;
  required: Array<string>;
  uiSchema: any;
  pipeline: any;
}

export const sanitiseTemplateForRJSF = (template: ResourceTemplate) => {
  if (template.properties) {
    Object.keys(template.properties).forEach((key: string) => {
      Object.keys(template.properties[key]).forEach((name: string) => {
        if (template.properties[key][name] === null) {
          delete template.properties[key][name];
        }
      });
    });
  }

  const sanitised = {
    name: template.name,
    type: template.type,
    description: template.description,
    title: template.title,
    properties: template.properties,
    allOf: template.allOf,
    required: template.required,
    uiSchema: template.uiSchema,
  };

  if (!sanitised.allOf) delete sanitised.allOf;

  return sanitised;
};

/**
 * Filters a template schema to only include properties with show_in_request: true.
 * Used to render a subset of template fields in the workspace request form.
 */
export const filterTemplateForRequest = (template: ResourceTemplate) => {
  const sanitised = sanitiseTemplateForRJSF(template);

  if (sanitised.properties) {
    const filtered: any = {};
    Object.keys(sanitised.properties).forEach((key: string) => {
      if (sanitised.properties[key].show_in_request === true) {
        filtered[key] = { ...sanitised.properties[key] };
        delete filtered[key].show_in_request;
      }
    });
    sanitised.properties = filtered;
  }

  // Remove required fields that aren't in the filtered properties
  if (sanitised.required && sanitised.properties) {
    sanitised.required = sanitised.required.filter(
      (r: string) => r in sanitised.properties,
    );
  }

  // Remove allOf conditionals since they reference properties not in the request form
  delete sanitised.allOf;

  return sanitised;
};

export interface TemplateAction {
  name: string;
  description: string;
}

// make a sensible guess at an icon
export const getActionIcon = (actionName: string) => {
  switch (actionName.toLowerCase()) {
    case "start":
      return "Play";
    case "stop":
      return "Stop";
    default:
      return "Asterisk";
  }
};
