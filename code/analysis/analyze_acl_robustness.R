#!/usr/bin/env Rscript

# Sensitivity analyses for the ACL-1 primary ordinal models:
# (1) participant-paired bootstrap contrasts and (2) linear mixed models.

suppressPackageStartupMessages({
  library(readr)
  library(jsonlite)
  library(lme4)
})

script_argument <- commandArgs(trailingOnly = FALSE)
script_path <- sub("^--file=", "", script_argument[grep("^--file=", script_argument)][1])
if (is.na(script_path) || !nzchar(script_path)) script_path <- "code/analysis/analyze_acl_robustness.R"
script_dir <- dirname(normalizePath(script_path, mustWork = FALSE))
project_dir <- normalizePath(file.path(script_dir, "..", ".."), mustWork = FALSE)
default_input <- file.path(project_dir, "data", "acl_human_evaluation_ratings.csv")
default_output <- file.path(project_dir, "analysis", "results", "robustness")

args <- commandArgs(trailingOnly = TRUE)
input <- if (length(args) >= 1) args[[1]] else default_input
output_dir <- if (length(args) >= 2) args[[2]] else default_output
if (!file.exists(input)) stop("Analysis snapshot not found: ", input)
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

ratings <- read_csv(input, show_col_types = FALSE)
if (!"session_id" %in% names(ratings) && "participant_code" %in% names(ratings)) {
  ratings$session_id <- ratings$participant_code
}
ratings$pipeline <- factor(
  substr(ratings$condition_code, 1, 1),
  levels = c("A", "C", "E"),
  labels = c("Direct Generation", "Script-Opposition-Guided Generation", "GTVH-Guided Generation")
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

participant_cell_means <- function(data, outcome) {
  aggregate(
    data[[outcome]],
    by = list(
      session_id = data$session_id,
      recruitment_source = data$recruitment_source,
      pipeline = data$pipeline,
      guidance = data$guidance
    ),
    FUN = mean
  )
}

contrast_matrix <- function(cell_means) {
  source_by_participant <- cell_means[
    !duplicated(cell_means$session_id),
    c("session_id", "recruitment_source")
  ]
  cell_means$cell <- paste(
    as.character(cell_means$pipeline),
    as.character(cell_means$guidance),
    sep = "__"
  )
  wide <- reshape(
    cell_means,
    idvar = "session_id",
    timevar = "cell",
    direction = "wide"
  )
  names(wide) <- sub("^x\\.", "", names(wide))
  wide <- merge(wide, source_by_participant, by = "session_id", sort = FALSE)
  required <- c(
    "Direct Generation__Neutral",
    "Direct Generation__Style-guided",
    "Script-Opposition-Guided Generation__Neutral",
    "Script-Opposition-Guided Generation__Style-guided",
    "GTVH-Guided Generation__Neutral",
    "GTVH-Guided Generation__Style-guided"
  )
  if (!all(required %in% names(wide))) stop("A participant is missing a pipeline-guidance cell.")
  data.frame(
    session_id = wide$session_id,
    recruitment_source = wide$recruitment_source,
    `Direct vs Script-Opposition` =
      rowMeans(wide[c("Direct Generation__Neutral", "Direct Generation__Style-guided")]) -
      rowMeans(wide[c("Script-Opposition-Guided Generation__Neutral", "Script-Opposition-Guided Generation__Style-guided")]),
    `Script-Opposition vs GTVH` =
      rowMeans(wide[c("Script-Opposition-Guided Generation__Neutral", "Script-Opposition-Guided Generation__Style-guided")]) -
      rowMeans(wide[c("GTVH-Guided Generation__Neutral", "GTVH-Guided Generation__Style-guided")]),
    `Style-guided vs Neutral` =
      rowMeans(wide[c("Direct Generation__Style-guided", "Script-Opposition-Guided Generation__Style-guided", "GTVH-Guided Generation__Style-guided")]) -
      rowMeans(wide[c("Direct Generation__Neutral", "Script-Opposition-Guided Generation__Neutral", "GTVH-Guided Generation__Neutral")]),
    check.names = FALSE
  )
}

bootstrap_contrast <- function(values, strata, repetitions = 10000, seed = 20260901) {
  set.seed(seed)
  boot <- replicate(repetitions, {
    sampled <- unlist(lapply(split(values, strata), function(group) {
      sample(group, length(group), replace = TRUE)
    }))
    mean(sampled)
  })
  test <- t.test(values, mu = 0)
  data.frame(
    estimate_likert_points = mean(values),
    ci_low = unname(quantile(boot, 0.025)),
    ci_high = unname(quantile(boot, 0.975)),
    paired_sd = sd(values),
    cohens_dz = mean(values) / sd(values),
    raw_p = test$p.value,
    participants = length(values)
  )
}

bootstrap_rows <- list()
for (outcome in names(outcomes)) {
  contrast_values <- contrast_matrix(participant_cell_means(ratings, outcome))
  for (contrast in contrast_names) {
    row <- bootstrap_contrast(
      contrast_values[[contrast]],
      contrast_values$recruitment_source,
      seed = 20260901 + length(bootstrap_rows)
    )
    row$outcome <- outcomes[[outcome]]
    row$contrast <- contrast
    bootstrap_rows[[length(bootstrap_rows) + 1]] <- row
  }
}
bootstrap_results <- do.call(rbind, bootstrap_rows)
bootstrap_results$analysis_role <- "supporting"
bootstrap_results$analysis_role[
  bootstrap_results$outcome == "Funniness" &
    bootstrap_results$contrast %in% c(
      "Direct vs Script-Opposition",
      "Script-Opposition vs GTVH"
    )
] <- "confirmatory"
bootstrap_results$analysis_role[
  bootstrap_results$outcome == "Perceived target-style alignment" &
    bootstrap_results$contrast == "Style-guided vs Neutral"
] <- "confirmatory"
bootstrap_results$holm_p_confirmatory_family <- NA_real_
bootstrap_confirmatory <- bootstrap_results$analysis_role == "confirmatory"
bootstrap_results$holm_p_confirmatory_family[bootstrap_confirmatory] <- p.adjust(
  bootstrap_results$raw_p[bootstrap_confirmatory],
  method = "holm"
)
write_csv(bootstrap_results, file.path(output_dir, "paired_bootstrap_contrasts.csv"))

contrast_vector <- function(contrast, beta_names) {
  vector <- setNames(rep(0, length(beta_names)), beta_names)
  required <- c(
    "pipelineScript-Opposition-Guided Generation",
    "pipelineGTVH-Guided Generation",
    "guidanceStyle-guided",
    "pipelineScript-Opposition-Guided Generation:guidanceStyle-guided",
    "pipelineGTVH-Guided Generation:guidanceStyle-guided"
  )
  if (!all(required %in% beta_names)) stop("Unexpected fixed-effect names in linear model.")
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

linear_rows <- list()
for (outcome in names(outcomes)) {
  fit <- lmer(
    as.formula(paste0(outcome, " ~ pipeline * guidance + recruitment_source + (1 | session_id) + (1 | item_id)")),
    data = ratings,
    REML = FALSE
  )
  beta <- fixef(fit)
  covariance <- vcov(fit)
  for (contrast in contrast_names) {
    vector <- contrast_vector(contrast, names(beta))
    estimate <- sum(vector * beta)
    standard_error <- sqrt(as.numeric(t(vector) %*% covariance %*% vector))
    z_value <- estimate / standard_error
    row <- data.frame(
      outcome = outcomes[[outcome]],
      contrast = contrast,
      estimate_likert_points = estimate,
      standard_error = standard_error,
      ci_low = estimate - 1.96 * standard_error,
      ci_high = estimate + 1.96 * standard_error,
      z_value = z_value,
      raw_p = 2 * pnorm(-abs(z_value)),
      observations = nrow(ratings),
      participants = nlevels(ratings$session_id),
      items = nlevels(ratings$item_id),
      aic = AIC(fit)
    )
    linear_rows[[length(linear_rows) + 1]] <- row
  }
  capture.output(summary(fit), file = file.path(output_dir, paste0(outcome, "_lmm.txt")))
}
linear_results <- do.call(rbind, linear_rows)
linear_results$analysis_role <- bootstrap_results$analysis_role
linear_results$holm_p_confirmatory_family <- NA_real_
linear_confirmatory <- linear_results$analysis_role == "confirmatory"
linear_results$holm_p_confirmatory_family[linear_confirmatory] <- p.adjust(
  linear_results$raw_p[linear_confirmatory],
  method = "holm"
)
write_csv(linear_results, file.path(output_dir, "linear_mixed_model_contrasts.csv"))

write_json(
  list(
    analysis = "ACL-1 robustness analyses",
    input = normalizePath(input),
    bootstrap = "10,000 participant-paired resamples per contrast",
    linear_model = "rating ~ pipeline * guidance + recruitment_source + (1 | participant) + (1 | item)",
    adjustment = "Holm across the three confirmatory tests; remaining outcome-contrast estimates are supporting.",
    recruitment_source = "Bootstrap resampling is stratified by the non-identifying recruitment-source field."
  ),
  file.path(output_dir, "robustness_metadata.json"),
  pretty = TRUE,
  auto_unbox = TRUE
)

message("Wrote robustness results to ", output_dir)
