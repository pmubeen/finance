terraform {
  # Configure the GCS backend for remote state storage
  backend "gcs" {
    bucket = "thinklab-d64b5-tfstate"       # Use the bucket name you created
    prefix = "terraform/state/finance/prod" # Use a prefix to separate environments
  }

  required_providers {
    google = {
      source = "hashicorp/google"
      # Use a pessimistic version constraint for safer provider updates
      version = "~> 6.14"
    }
  }
}

locals {
  project = "thinklab-d64b5"
  region  = "us-central1"
}

provider "google" {
  project = local.project
  region  = local.region
  default_labels = {
    "app" = "fincs50"
  }
}

resource "google_cloud_run_service" "finance-service" {
  name     = "fincs50"
  location = "us-central1"
  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale"     = "5"
        "run.googleapis.com/client-name"       = "cloud-console"
        "run.googleapis.com/startup-cpu-boost" = "true"
      }
    }
    spec {
      container_concurrency = 1
      timeout_seconds       = 300
      service_account_name  = "488815099222-compute@developer.gserviceaccount.com"
      containers {
        name  = "fincs50"
        image = "gcr.io/thinklab-d64b5/fincs50:latest"
        ports {
          name           = "http1"
          container_port = 8000
        }
        resources {
          limits = {
            "cpu"    = "500m"
            "memory" = "256Mi"
          }
        }
        startup_probe {
          timeout_seconds   = 240
          period_seconds    = 240
          failure_threshold = 1
          tcp_socket {
            port = 8000
          }
        }
        liveness_probe {
          timeout_seconds   = 5
          period_seconds    = 10
          failure_threshold = 3
          http_get {
            path = "/"
            port = 8000
          }
        }
        command = ["gunicorn"]
        args = [
          "--bind", "0.0.0.0:8000",
          "--workers", "1",
          "--timeout", "120",
          "app:app"
        ]
        env {
          name  = "ALPHA_VANTAGE_API_KEY"
          value = var.ALPHA_VANTAGE_API_KEY
        }
        env {
          name  = "FMP_API_KEY"
          value = var.FMP_API_KEY
        }
      }
    }
  }
}

resource "google_cloud_run_domain_mapping" "finance-domain-mapping" {
  location = "us-central1"
  name     = "fincs50.itsmubeen.me"

  metadata {
    namespace = local.project
  }

  spec {
    route_name       = google_cloud_run_service.finance-service.name
    certificate_mode = "AUTOMATIC"
  }
}
