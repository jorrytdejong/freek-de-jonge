#!/usr/bin/env Rscript

# Primary ordinal mixed-effects analysis for the ACL-1 human-evaluation study.
# The input snapshot contains only the fields needed for modelling; it excludes
# joke text and free-text comments. Ratings are treated as ordered 1--5 values.

suppressPackageStartupMessages({
  library(ordinal)
  library(readr)
  library(jsonlite)
})

script_argument <- commandArgs(trailingOnly = FALSE)
script_path <- sub("^--file=", "", script_argument[grep("^--file=", script_argument)][1])
if (is.na(script_path) || !nzchar(script_path)) script_path <- "code/analysis/analyze_acl_ordinal.R"
script_dir <- dirname(normalizePath(script_path, mustWork = FALSE))
project_dir <- normalizePath(file.path(script_dir, "..", ".."), mustWork = FALSE)
default_input <- file.path(project_dir, "data", "acl_human_evaluation_ratings.csv")
default_output <- file.path(project_dir, "analysis", "results", "ordinal_models")

args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args) >= 1) args[[1]] else default_input
output_dir <- if (length(args) >= 2) args[[2]] else default_output

if (!file.exists(input)) stop("Analysis snapshot not found: ", input)
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

ratings <- read_csv(input, show_col_types = FALSE)
if (!"session_id" %in% names(ratings) && "participant_code" %in% names(ratings)) {
  ratings$session_id <- ratings$participant_code
}
required <- c(
  "session_id", "item_id", "condition_code", "funniness",
  "freek_similarity", "coherence", "freek_familiarity", "recruitment_source"
)
missing <- setdiff(required, names(ratings))
if (length(missing)) stop("Missing columns: ", paste(missing, collapse = ", "))
if (nrow(ratings) == 0) stop("The analysis snapshot has no rows.")

ratings$pipeline <- factor(
  substr(ratings$condition_code, 1, 1),
  levels = c("A", "C", "E"),
  labels = c(
    "Direct Generation",
    "Script-Opposition-Guided Generation",
    "GTVH-Guided Generation"
  )
)
ratings$guidance <- factor(
  substr(ratings$condition_code, 2, 2),
  levels = c("1", "2"),
  labels = c("Neutral", "Style-guided")
)
ratings$session_id <- factor(ratings$session_id)
ratings$item_id <- factor(ratings$item_id)
ratings$recruitment_source <- factor(
  ratings$recruitment_source,
  levels = c("network", "prolific"),
  labels = c("Network", "Prolific")
)
ratings$familiarity_centered <- ratings$freek_familiarity - mean(ratings$freek_familiarity)

for (outcome in c("funniness", "freek_similarity", "coherence")) {
  values <- ratings[[outcome]]
  if (any(is.na(values)) || any(values < 1 | values > 5) || any(values != floor(values))) {
    stop("Invalid ordinal ratings in ", outcome)
  }
}

outcomes <- c(
  funniness = "Funniness",
  freek_similarity = "Perceived target-style alignment",
  coherence = "Coherence"
)
contrast_names <- c(
  "Direct vs Script-Opposition",
  "Script-Opposition vs GTVH",
  "Style-guided vs Neutral"
)

contrast_vector <- function(contrast, beta_names) {
  vector <- setNames(rep(0, length(beta_names)), beta_names)
  needed <- c(
    "pipelineScript-Opposition-Guided Generation",
    "pipelineGTVH-Guided Generation",
    "guidanceStyle-guided",
    "pipelineScript-Opposition-Guided Generation:guidanceStyle-guided",
    "pipelineGTVH-Guided Generation:guidanceStyle-guided"
  )
  if (!all(needed %in% beta_names)) stop("Unexpected fixed-effect names in ordinal model.")
  if (contrast == "Direct vs Script-Opposition") {
    vector["pipelineScript-Opposition-Guided Generation"] <- -1
    vector["pipelineScript-Opposition-Guided Generation:guidanceStyle-guided"] <- -0.5
  } else if (contrast == "Script-Opposition vs GTVH") {
    vector["pipelineScript-Opposition-Guided Generation"] <- 1
    vector["pipelineGTVH-Guided Generation"] <- -1
    vector["pipelineScript-Opposition-Guided Generation:guidanceStyle-guided"] <- 0.5
    vector["pipelineGTVH-Guided Generation:guidanceStyle-guided"] <- -0.5
  } else if (contrast == "Style-guided vs Neutral") {
    vector["guidanceStyle-guided"] <- 1
    vector["pipelineScript-Opposition-Guided Generation:guidanceStyle-guided"] <- 1 / 3
    vector["pipelineGTVH-Guided Generation:guidanceStyle-guided"] <- 1 / 3
  }
  vector
}

analysis_role <- function(outcome, contrast) {
  if (
    (outcome == "Funniness" && contrast %in% c("Direct vs Script-Opposition", "Script-Opposition vs GTVH")) ||
      (outcome == "Perceived target-style alignment" && contrast == "Style-guided vs Neutral")
  ) "confirmatory" else "supporting"
}

all_coefficients <- list()
model_index <- list()
contrast_rows <- list()

for (outcome in names(outcomes)) {
  model_data <- ratings
  model_data$response <- ordered(model_data[[outcome]], levels = 1:5)
  fit <- clmm(
    response ~ pipeline * guidance + recruitment_source + (1 | session_id) + (1 | item_id),
    data = model_data,
    link = "logit",
    nAGQ = 1,
    Hess = TRUE
  )

  coefficient_table <- as.data.frame(coef(summary(fit)))
  coefficient_table$term <- rownames(coefficient_table)
  rownames(coefficient_table) <- NULL
  names(coefficient_table)[1:2] <- c("estimate_log_odds", "standard_error")
  coefficient_table$odds_ratio <- exp(coefficient_table$estimate_log_odds)
  coefficient_table$ci_low <- exp(coefficient_table$estimate_log_odds - 1.96 * coefficient_table$standard_error)
  coefficient_table$ci_high <- exp(coefficient_table$estimate_log_odds + 1.96 * coefficient_table$standard_error)
  coefficient_table$outcome <- outcomes[[outcome]]
  all_coefficients[[outcome]] <- coefficient_table

  beta <- fit$beta
  covariance <- vcov(fit)[names(beta), names(beta), drop = FALSE]
  for (contrast in contrast_names) {
    vector <- contrast_vector(contrast, names(beta))
    estimate <- sum(vector * beta)
    standard_error <- sqrt(as.numeric(t(vector) %*% covariance %*% vector))
    z_value <- estimate / standard_error
    contrast_rows[[length(contrast_rows) + 1]] <- data.frame(
      outcome = outcomes[[outcome]],
      contrast = contrast,
      estimate_log_odds = estimate,
      standard_error = standard_error,
      odds_ratio = exp(estimate),
      ci_low = exp(estimate - 1.96 * standard_error),
      ci_high = exp(estimate + 1.96 * standard_error),
      z_value = z_value,
      raw_p = 2 * pnorm(-abs(z_value)),
      analysis_role = analysis_role(outcomes[[outcome]], contrast)
    )
  }

  model_index[[outcome]] <- list(
    outcome = outcomes[[outcome]],
    observations = nrow(model_data),
    participants = nlevels(model_data$session_id),
    items = nlevels(model_data$item_id),
    log_likelihood = as.numeric(logLik(fit)),
    aic = AIC(fit),
    convergence = fit$convergence
  )
  capture.output(summary(fit), file = file.path(output_dir, paste0(outcome, "_clmm.txt")))
}

coefficients <- do.call(rbind, all_coefficients)
write_csv(coefficients, file.path(output_dir, "ordinal_model_coefficients.csv"))
planned_contrasts <- do.call(rbind, contrast_rows)
planned_contrasts$holm_p_confirmatory_family <- NA_real_
confirmatory <- planned_contrasts$analysis_role == "confirmatory"
planned_contrasts$holm_p_confirmatory_family[confirmatory] <- p.adjust(
  planned_contrasts$raw_p[confirmatory],
  method = "holm"
)
write_csv(planned_contrasts, file.path(output_dir, "ordinal_model_planned_contrasts.csv"))

familiarity_data <- ratings
familiarity_data$response <- ordered(familiarity_data$freek_similarity, levels = 1:5)
familiarity_fit <- clmm(
  response ~ pipeline * guidance + recruitment_source +
    familiarity_centered * guidance + (1 | session_id) + (1 | item_id),
  data = familiarity_data,
  link = "logit",
  nAGQ = 1,
  Hess = TRUE
)
familiarity_table <- as.data.frame(coef(summary(familiarity_fit)))
familiarity_table$term <- rownames(familiarity_table)
rownames(familiarity_table) <- NULL
names(familiarity_table)[1:2] <- c("estimate_log_odds", "standard_error")
familiarity_table$odds_ratio <- exp(familiarity_table$estimate_log_odds)
familiarity_table$ci_low <- exp(familiarity_table$estimate_log_odds - 1.96 * familiarity_table$standard_error)
familiarity_table$ci_high <- exp(familiarity_table$estimate_log_odds + 1.96 * familiarity_table$standard_error)
write_csv(familiarity_table, file.path(output_dir, "familiarity_exploratory_style_model.csv"))
capture.output(summary(familiarity_fit), file = file.path(output_dir, "familiarity_exploratory_style_model.txt"))

write_json(
  list(
    analysis = "ACL-1 cumulative-link ordinal mixed-effects models",
    input = normalizePath(input),
    model = "rating ~ pipeline * guidance + recruitment_source + (1 | participant) + (1 | item)",
    link = "logit",
    integration = "Laplace approximation (nAGQ = 1)",
    recruitment_source = "Non-identifying recruitment-source field included in the public ratings CSV.",
    multiplicity_adjustment = "Holm across the three confirmatory planned contrasts.",
    familiarity_analysis = "Exploratory style-alignment model with centered familiarity and familiarity-by-guidance interaction.",
    models = model_index
  ),
  file.path(output_dir, "ordinal_model_metadata.json"),
  pretty = TRUE,
  auto_unbox = TRUE
)

message("Wrote ordinal-model results to ", output_dir)
