output "event_grid_status_changed_topic_endpoint" {
  value = azurerm_eventgrid_topic.status_changed.endpoint
}

output "event_grid_airlock_notification_topic_endpoint" {
  value = azurerm_eventgrid_topic.airlock_notification.endpoint
}

output "event_grid_status_changed_topic_resource_id" {
  value = azurerm_eventgrid_topic.status_changed.id
}

output "event_grid_airlock_notification_topic_resource_id" {
  value = azurerm_eventgrid_topic.airlock_notification.id
}
