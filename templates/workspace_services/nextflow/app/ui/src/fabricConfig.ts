// Imported before @fluentui/react: the workspace has no internet access, so Fluent must not
// register CDN font faces, and icon fonts are served from this app (see scripts/copy-icons.mjs).
(window as unknown as { FabricConfig: object }).FabricConfig = { fontBaseUrl: "", iconBaseUrl: "/fluent-icons/" };

export {};
