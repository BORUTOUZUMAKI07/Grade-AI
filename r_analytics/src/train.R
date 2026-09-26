# Make paths independent of the caller working directory.
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grepl("^--file=", args)][1])
script_dir <- dirname(normalizePath(file_arg, winslash = "/", mustWork = TRUE))
setwd(normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE))
source("src/config.R")
source("src/utils.R")

if (!requireNamespace("rpart", quietly = TRUE)) install.packages("rpart", repos="https://cloud.r-project.org")
if (!requireNamespace("jsonlite", quietly = TRUE)) install.packages("jsonlite", repos="https://cloud.r-project.org")


# Reproducible stratified hold-out evaluation. Final production artifacts below are
# still fit on all rows; this split is reserved for an honest generalization estimate.
evaluate_binary <- function(actual, predicted, score) {
  actual <- factor(as.character(actual), levels=c("Fail", "Pass"))
  predicted <- factor(as.character(predicted), levels=c("Fail", "Pass"))
  tp <- sum(actual == "Pass" & predicted == "Pass")
  tn <- sum(actual == "Fail" & predicted == "Fail")
  fp <- sum(actual == "Fail" & predicted == "Pass")
  fn <- sum(actual == "Pass" & predicted == "Fail")
  precision <- if ((tp + fp) == 0) 0 else tp / (tp + fp)
  recall <- if ((tp + fn) == 0) 0 else tp / (tp + fn)
  specificity <- if ((tn + fp) == 0) 0 else tn / (tn + fp)
  f1 <- if ((precision + recall) == 0) 0 else 2 * precision * recall / (precision + recall)
  # Pairwise rank AUC; ties contribute 0.5.
  pos <- score[actual == "Pass"]; neg <- score[actual == "Fail"]
  auc <- if (length(pos) && length(neg)) {
    mean(outer(pos, neg, function(p, n) ifelse(p > n, 1, ifelse(p == n, 0.5, 0))))
  } else NA_real_
  calibration_bins <- cut(score, breaks=seq(0, 1, by=0.2),
                           include.lowest=TRUE, right=TRUE,
                           labels=c("0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"))
  bin_rows <- lapply(levels(calibration_bins), function(bin) {
    idx <- which(calibration_bins == bin)
    list(bin=bin, count=length(idx),
         mean_predicted=if(length(idx)) mean(score[idx]) else NA_real_,
         observed_pass_rate=if(length(idx)) mean(actual[idx] == "Pass") else NA_real_)
  })
  nonempty <- which(vapply(bin_rows, function(x) x$count > 0, logical(1)))
  ece <- if(length(nonempty)) sum(vapply(nonempty, function(i)
    bin_rows[[i]]$count / length(actual) *
      abs(bin_rows[[i]]$mean_predicted - bin_rows[[i]]$observed_pass_rate), numeric(1))) else NA_real_
  # Average precision (stepwise PR-AUC) over descending predicted scores.
  ord <- order(score, decreasing=TRUE)
  sorted_actual <- as.numeric(actual[ord] == "Pass")
  cumulative_tp <- cumsum(sorted_actual)
  precision_at_rank <- cumulative_tp / seq_along(sorted_actual)
  pr_auc <- if (sum(sorted_actual) > 0) {
    sum(precision_at_rank * sorted_actual) / sum(sorted_actual)
  } else NA_real_
  eps <- 1e-15
  clipped <- pmin(1-eps, pmax(eps, score))
  log_loss <- mean(-((actual == "Pass") * log(clipped) +
                     (actual == "Fail") * log(1-clipped)))
  list(n=length(actual), accuracy=mean(actual == predicted),
       balanced_accuracy=(recall + specificity) / 2,
       precision=precision, recall=recall, specificity=specificity, f1=f1,
       roc_auc=auc, pr_auc=pr_auc, log_loss=log_loss,
       confusion_matrix=list(
         labels=c("Fail", "Pass"),
         rows=list(actual_Fail=list(predicted_Fail=tn, predicted_Pass=fp),
                   actual_Pass=list(predicted_Fail=fn, predicted_Pass=tp))),
       baseline_majority_accuracy=max(mean(actual == "Pass"), mean(actual == "Fail")),
       brier_score=mean((score - as.numeric(actual == "Pass"))^2),
       calibration= list(expected_calibration_error=ece, bins=bin_rows,
         note="Descriptive 5-bin calibration check on the held-out split only; no calibration model was fitted."))
}

make_holdout <- function(data) {
  set.seed(20260925)
  train_idx <- integer(0); test_idx <- integer(0)
  for (label in levels(data$Result)) {
    idx <- which(data$Result == label)
    idx <- sample(idx)
    n_test <- max(1, floor(length(idx) * 0.2))
    if (length(idx) - n_test < 1) stop("Each class needs at least two rows for stratified hold-out.")
    test_idx <- c(test_idx, idx[seq_len(n_test)])
    train_idx <- c(train_idx, idx[(n_test + 1):length(idx)])
  }
  list(train=data[train_idx, , drop=FALSE], test=data[test_idx, , drop=FALSE],
       seed=20260925, train_rows=length(train_idx), test_rows=length(test_idx))
}

main <- function() {
  cat("Training GradeAI model suite...\n")
  if (!file.exists(CONFIG$data_path)) stop(paste("Dataset not found:", CONFIG$data_path))
  students <- read.csv(CONFIG$data_path)
  required <- c("StudyHours", "Attendance", "PreviousMarks", "Result")
  missing <- setdiff(required, names(students))
  if (length(missing)) stop(paste("Missing required columns:", paste(missing, collapse=", ")))
  if (any(!complete.cases(students[, required]))) stop("Dataset contains missing values; regenerate and validate it first.")
  if (!all(students$Result %in% c("Fail", "Pass"))) stop("Result must contain only Fail or Pass.")
  students$Result <- factor(students$Result, levels=c("Fail", "Pass"))
  if (nrow(students) != 1000L || any(table(students$Result) != 500L))
    stop("Expected exactly 1,000 synthetic demo rows: 500 Fail and 500 Pass. Run data/generate_balanced_dataset.py first.")
  if (any(students$StudyHours < 0 | students$StudyHours > 12) ||
      any(students$Attendance < 40 | students$Attendance > 100) ||
      any(students$PreviousMarks < 0 | students$PreviousMarks > 100))
    stop("Dataset contains feature values outside the generator's documented ranges.")
  dir.create(CONFIG$output_dir, recursive=TRUE, showWarnings=FALSE)

  # Evaluate on a stratified hold-out that is never used to fit these evaluation models.
  split <- make_holdout(students)
  eval_tree <- rpart::rpart(Result ~ StudyHours + Attendance + PreviousMarks,
                            data=split$train, method="class",
                            control=rpart::rpart.control(cp=0.01))
  tree_score <- as.numeric(stats::predict(eval_tree, split$test, type="prob")[, "Pass"])
  tree_pred <- ifelse(tree_score >= 0.5, "Pass", "Fail")
  tree_eval <- evaluate_binary(split$test$Result, tree_pred, tree_score)

  # Logistic Regression evaluation fit uses only the training partition.
  eval_x_train <- split$train[, c("StudyHours", "Attendance", "PreviousMarks")]
  eval_x_test <- split$test[, c("StudyHours", "Attendance", "PreviousMarks")]
  eval_center <- vapply(eval_x_train, mean, numeric(1))
  eval_scale <- vapply(eval_x_train, stats::sd, numeric(1))
  eval_scale[!is.finite(eval_scale) | eval_scale == 0] <- 1
  eval_train <- as.data.frame(scale(eval_x_train, center=eval_center, scale=eval_scale))
  names(eval_train) <- c("StudyHours", "Attendance", "PreviousMarks")
  eval_train$Result <- split$train$Result
  eval_test <- as.data.frame(scale(eval_x_test, center=eval_center, scale=eval_scale))
  names(eval_test) <- c("StudyHours", "Attendance", "PreviousMarks")
  eval_logit <- stats::glm(Result ~ StudyHours + Attendance + PreviousMarks,
                           data=eval_train, family=stats::binomial())
  logit_score <- as.numeric(stats::predict(eval_logit, newdata=eval_test, type="response"))
  logit_pred <- ifelse(logit_score >= 0.5, "Pass", "Fail")
  logit_eval <- evaluate_binary(split$test$Result, logit_pred, logit_score)

  # Five-fold stratified CV on the outer training partition only.
  # The outer test partition remains untouched by CV and model selection.
  set.seed(20260926)
  cv_fold_id <- integer(nrow(split$train))
  for (label in levels(split$train$Result)) {
    idx <- which(split$train$Result == label)
    idx <- sample(idx)
    cv_fold_id[idx] <- rep(seq_len(5), length.out=length(idx))
  }
  cv_rows <- lapply(seq_len(5), function(fold) {
    cv_train <- split$train[cv_fold_id != fold, , drop=FALSE]
    cv_valid <- split$train[cv_fold_id == fold, , drop=FALSE]
    tree_cv <- rpart::rpart(Result ~ StudyHours + Attendance + PreviousMarks,
                            data=cv_train, method="class",
                            control=rpart::rpart.control(cp=0.01, maxdepth=5, minbucket=10))
    tree_prob <- as.numeric(stats::predict(tree_cv, cv_valid, type="prob")[, "Pass"])
    tree_hat <- ifelse(tree_prob >= 0.5, "Pass", "Fail")
    cv_x <- cv_train[, c("StudyHours", "Attendance", "PreviousMarks")]
    cv_center <- vapply(cv_x, mean, numeric(1))
    cv_scale <- vapply(cv_x, stats::sd, numeric(1))
    cv_scale[!is.finite(cv_scale) | cv_scale == 0] <- 1
    cv_train_scaled <- as.data.frame(scale(cv_x, center=cv_center, scale=cv_scale))
    names(cv_train_scaled) <- c("StudyHours", "Attendance", "PreviousMarks")
    cv_train_scaled$Result <- cv_train$Result
    cv_valid_scaled <- as.data.frame(scale(cv_valid[, c("StudyHours", "Attendance", "PreviousMarks")],
                                           center=cv_center, scale=cv_scale))
    names(cv_valid_scaled) <- c("StudyHours", "Attendance", "PreviousMarks")
    logit_cv <- stats::glm(Result ~ StudyHours + Attendance + PreviousMarks,
                           data=cv_train_scaled, family=stats::binomial())
    logit_prob <- as.numeric(stats::predict(logit_cv, newdata=cv_valid_scaled, type="response"))
    logit_hat <- ifelse(logit_prob >= 0.5, "Pass", "Fail")
    actual <- as.character(cv_valid$Result)
    list(fold=fold,
         decision_tree=list(n=length(actual), accuracy=mean(tree_hat==actual),
                            log_loss=mean(-((actual=="Pass")*log(pmax(tree_prob,1e-15))+
                                            (actual=="Fail")*log(pmax(1-tree_prob,1e-15))))),
         logistic_regression=list(n=length(actual), accuracy=mean(logit_hat==actual),
                            log_loss=mean(-((actual=="Pass")*log(pmax(logit_prob,1e-15))+
                                            (actual=="Fail")*log(pmax(1-logit_prob,1e-15))))))
  })
  summarize_cv <- function(key, metric) {
    vals <- vapply(cv_rows, function(row) row[[key]][[metric]], numeric(1))
    list(mean=mean(vals), sd=stats::sd(vals), fold_values=as.list(vals))
  }
  cv_summary <- list(folds=5, data="outer training partition only",
                     decision_tree=list(accuracy=summarize_cv("decision_tree","accuracy"),
                                        log_loss=summarize_cv("decision_tree","log_loss")),
                     logistic_regression=list(accuracy=summarize_cv("logistic_regression","accuracy"),
                                              log_loss=summarize_cv("logistic_regression","log_loss")),
                     note="Fold-level estimates are computed only within the outer training partition; final reported hold-out metrics use the untouched test partition.")

  # 1) Decision Tree classifier (existing API-compatible export) (existing API-compatible export)
  tree <- rpart::rpart(Result ~ StudyHours + Attendance + PreviousMarks,
                       data=students, method="class", control=rpart::rpart.control(cp=0.01))
  export_tree_meta(tree, students, CONFIG$output_dir, CONFIG$tree_filename)

  # 2) Logistic Regression classifier, standardized using full approved training data.
  x <- students[, c("StudyHours", "Attendance", "PreviousMarks")]
  feature_center <- vapply(x, mean, numeric(1))
  feature_scale <- vapply(x, stats::sd, numeric(1))
  feature_scale[!is.finite(feature_scale) | feature_scale == 0] <- 1
  x_scaled <- as.data.frame(scale(x, center=feature_center, scale=feature_scale))
  names(x_scaled) <- c("StudyHours", "Attendance", "PreviousMarks")
  x_scaled$Result <- students$Result
  logistic <- stats::glm(Result ~ StudyHours + Attendance + PreviousMarks,
                         data=x_scaled, family=stats::binomial())
  co <- stats::coef(logistic)
  logistic_payload <- list(
    metadata=list(name="Logistic Regression", framework="R stats::glm binomial",
                  trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
                  total_records=nrow(students), target="Pass/Fail",
                  note="Synthetic demo classifier; probabilities are not calibrated for real student outcomes."),
    center=as.list(setNames(as.numeric(feature_center), c("study_hours", "attendance", "previous_marks"))),
    scale=as.list(setNames(as.numeric(feature_scale), c("study_hours", "attendance", "previous_marks"))),
    weights=list(intercept=unname(co[1]), study_hours=unname(co["StudyHours"]),
                 attendance=unname(co["Attendance"]), previous_marks=unname(co["PreviousMarks"]))
  )
  jsonlite::write_json(logistic_payload, file.path(CONFIG$output_dir, "logistic_regression_model.json"),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)

  # 3) PCA on standardized numeric inputs; save loadings, center, scale and variance.
  feature_sd <- vapply(x, stats::sd, numeric(1))
  if (any(!is.finite(feature_sd) | feature_sd == 0)) {
    stop("PCA/K-Means require non-constant numeric features: ",
         paste(names(feature_sd)[!is.finite(feature_sd) | feature_sd == 0], collapse=", "))
  }
  scaled <- scale(x)
  pca <- stats::prcomp(x, center=TRUE, scale.=TRUE)
  pca_payload <- list(
    metadata=list(name="PCA", framework="R stats::prcomp", trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
                  total_records=nrow(students), explained_variance=round(pca$sdev^2/sum(pca$sdev^2), 6)),
    center=as.list(pca$center), scale=as.list(pca$scale),
    loadings=lapply(seq_len(ncol(pca$rotation)), function(i) as.list(pca$rotation[, i])),
    loading_names=rownames(pca$rotation), scores=unname(pca$x[, 1:2, drop=FALSE]),
    score_columns=c("PC1", "PC2"),
    components_retained=2
  )
  jsonlite::write_json(pca_payload, file.path(CONFIG$output_dir, CONFIG$pca_filename),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)

  # 4) K-Means on standardized inputs. Fix seed for repeatable demo clusters.
  set.seed(CONFIG$cluster_seed)
  k <- 2L
  km <- stats::kmeans(scaled, centers=k, nstart=25)
  cluster_payload <- list(
    metadata=list(name="K-Means Clustering", framework="R stats::kmeans",
                  trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
                  total_records=nrow(students), clusters=k, features=names(x)),
    centers=unname(km$centers), cluster_sizes=as.list(km$size),
    records=lapply(seq_len(nrow(students)), function(i) list(
      study_hours=students$StudyHours[i], attendance=students$Attendance[i],
      previous_marks=students$PreviousMarks[i], result=as.character(students$Result[i]),
      cluster=as.integer(km$cluster[i])
    ))
  )
  jsonlite::write_json(cluster_payload, file.path(CONFIG$output_dir, CONFIG$clusters_filename),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)

  # One summary document powers the model registry/analytics UI.
  analytics <- list(
    dataset_note="Synthetic demo dataset. Decision Tree and Logistic Regression validation metrics use a reproducible stratified 80/20 hold-out. Final artifacts are then refit on all rows. PCA (2 components) and K-Means (2 clusters) are unsupervised; cluster pass rates are descriptive historical profiles, not standalone classifiers.",
    data_source="r_analytics/data/student_data.csv (synthetic demo data)",
    trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"), total_records=nrow(students),
    validation=list(method="stratified 80/20 hold-out with 5-fold stratified CV on training partition", seed=split$seed,
                    train_rows=split$train_rows, test_rows=split$test_rows,
                    positive_class="Pass", threshold=0.5,
                    decision_tree=tree_eval, logistic_regression=logit_eval,
                    cross_validation=cv_summary,
                    unsupervised_note="PCA (2 components) and K-Means (2 clusters) are not evaluated as standalone Pass/Fail classifiers; no accuracy, F1 or AUC is assigned to them. Cluster outcome profiles are descriptive training-set summaries and must not be treated as validated risk estimates."),
    result_counts=as.list(table(students$Result)),
    feature_summary=lapply(x, function(v) list(min=min(v), max=max(v), mean=mean(v), median=median(v), sd=stats::sd(v))),
    tree=list(accuracy=mean(stats::predict(tree, students, type="class")==students$Result),
              variable_importance=if (is.null(tree$variable.importance)) list() else as.list(tree$variable.importance)),
    logistic_regression=logistic_payload$metadata,
    pca=pca_payload$metadata,
    clustering=km$size
  )
  jsonlite::write_json(analytics, file.path(CONFIG$output_dir, CONFIG$analytics_filename),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)
  cat("Trained and exported Decision Tree, Logistic Regression, PCA, K-Means and analytics artifacts.\n")
}
main()
