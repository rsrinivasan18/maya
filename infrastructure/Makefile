SHELL  := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

REGION  := ap-southeast-1
ACCOUNT := 221227165737
ENV_FILE := ../.env
TFVARS   := terraform.tfvars
SERVICE  := maya-web

# ── Helpers ───────────────────────────────────────────────────────────────────

# Read a key from ../.env  (strips quotes, ignores comment lines)
define env_val
$(shell grep -E '^$(1)=' $(ENV_FILE) | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
endef

# Read a key from terraform.tfvars  (strips quotes)
define tfvar_val
$(shell grep -E '^$(1)\s*=' $(TFVARS) | head -1 | sed 's/.*=\s*//' | tr -d '"' | tr -d "'" | tr -d ' ')
endef

# ── Targets ───────────────────────────────────────────────────────────────────

.PHONY: help
help:
	@echo ""
	@echo "  MAYA Infrastructure Makefile"
	@echo "  Region: $(REGION)  Account: $(ACCOUNT)"
	@echo ""
	@echo "  Targets:"
	@echo "    make fill-secrets     — push all 6 secrets from .env + tfvars to AWS"
	@echo "    make get-rds-endpoint — print the RDS hostname"
	@echo "    make redeploy         — delete failed App Runner service + terraform apply"
	@echo "    make all              — fill-secrets then redeploy"
	@echo ""

# ── get-rds-endpoint ──────────────────────────────────────────────────────────

.PHONY: get-rds-endpoint
get-rds-endpoint:
	@aws rds describe-db-instances \
		--db-instance-identifier maya-db \
		--query 'DBInstances[0].Endpoint.Address' \
		--output text \
		--region $(REGION)

# ── fill-secrets ──────────────────────────────────────────────────────────────

.PHONY: fill-secrets
fill-secrets:
	@echo "==> Reading values..."

	$(eval ANTHROPIC_KEY := $(call env_val,ANTHROPIC_API_KEY))
	$(eval SARVAM_KEY    := $(call env_val,SARVAM_API_KEY))
	$(eval DB_PASSWORD   := $(call tfvar_val,db_password))

	@if [ -z "$(ANTHROPIC_KEY)" ]; then echo "ERROR: ANTHROPIC_API_KEY not found in $(ENV_FILE)"; exit 1; fi
	@if [ -z "$(SARVAM_KEY)" ];    then echo "ERROR: SARVAM_API_KEY not found in $(ENV_FILE)"; exit 1; fi
	@if [ -z "$(DB_PASSWORD)" ];   then echo "ERROR: db_password not found in $(TFVARS)"; exit 1; fi

	@echo "==> Fetching RDS endpoint..."
	$(eval RDS_ENDPOINT := $(shell aws rds describe-db-instances \
		--db-instance-identifier maya-db \
		--query 'DBInstances[0].Endpoint.Address' \
		--output text \
		--region $(REGION) 2>/dev/null))

	@if [ -z "$(RDS_ENDPOINT)" ] || [ "$(RDS_ENDPOINT)" = "None" ]; then \
		echo "ERROR: Could not get RDS endpoint. Is maya-db running?"; exit 1; \
	fi

	@echo "==> RDS endpoint: $(RDS_ENDPOINT)"
	@echo ""

	@echo "==> Filling /maya/anthropic-api-key..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/anthropic-api-key \
		--secret-string "$(ANTHROPIC_KEY)" \
		--region $(REGION) --output none

	@echo "==> Filling /maya/sarvam-api-key..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/sarvam-api-key \
		--secret-string "$(SARVAM_KEY)" \
		--region $(REGION) --output none

	@echo "==> Filling /maya/sarvam-api-url..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/sarvam-api-url \
		--secret-string "https://api.sarvam.ai" \
		--region $(REGION) --output none

	@echo "==> Filling /maya/connectivity-host..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/connectivity-host \
		--secret-string "api.anthropic.com" \
		--region $(REGION) --output none

	@echo "==> Filling /maya/connectivity-port..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/connectivity-port \
		--secret-string "443" \
		--region $(REGION) --output none

	@echo "==> Filling /maya/database-url..."
	@aws secretsmanager put-secret-value \
		--secret-id /maya/database-url \
		--secret-string "postgresql://mayaadmin:$(DB_PASSWORD)@$(RDS_ENDPOINT)/mayadb?sslmode=require" \
		--region $(REGION) --output none

	@echo ""
	@echo "All 6 secrets filled successfully."
	@echo "Next: redeploy App Runner so it picks up the new secret values."
	@echo "  make redeploy"

# ── redeploy ──────────────────────────────────────────────────────────────────

.PHONY: redeploy
redeploy:
	@echo "==> Checking for existing App Runner service..."

	$(eval SERVICE_ARN := $(shell aws apprunner list-services \
		--region $(REGION) \
		--query "ServiceSummaryList[?ServiceName=='$(SERVICE)'].ServiceArn" \
		--output text 2>/dev/null))

	@if [ -n "$(SERVICE_ARN)" ] && [ "$(SERVICE_ARN)" != "None" ]; then \
		echo "==> Deleting App Runner service: $(SERVICE_ARN)"; \
		aws apprunner delete-service \
			--service-arn "$(SERVICE_ARN)" \
			--region $(REGION) --output none; \
		echo "==> Waiting for deletion (this takes ~60s)..."; \
		aws apprunner wait service-deleted \
			--service-arn "$(SERVICE_ARN)" \
			--region $(REGION) 2>/dev/null || \
		(echo "wait command not available, sleeping 90s..." && sleep 90); \
		echo "==> Service deleted."; \
	else \
		echo "==> No existing service found, skipping delete."; \
	fi

	@echo "==> Running terraform apply..."
	@terraform apply -auto-approve

	@echo ""
	@echo "Redeploy complete. App Runner URL:"
	@terraform output app_runner_url

# ── all ───────────────────────────────────────────────────────────────────────

.PHONY: all
all: fill-secrets redeploy
