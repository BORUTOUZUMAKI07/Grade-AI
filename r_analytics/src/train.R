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
  list(n=length(actual), accuracy=mean(actual == predicted),
       precision=precision, recall=recall, specificity=specificity, f1=f1,
       roc_auc=auc, confusion_matrix=list(
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
  students <- students[complete.cases(students[, required]), ]
  students$Result <- factor(students$Result, levels=c("Fail", "Pass"))
  if (nrow(students) < 4) stop("At least four complete student rows are required.")
  dir.create(CONFIG$output_dir, recursive=TRUE, showWarnings=FALSE)

  # Evaluate on a stratified hold-out that is never used to fit these evaluation models.
  split <- make_holdout(students)
  eval_tree <- rpart::rpart(Result ~ StudyHours + Attendance + PreviousMarks,
                            data=split$train, method="class",
                            control=rpart::rpart.control(cp=0.01))
  tree_score <- as.numeric(stats::predict(eval_tree, split$test, type="prob")[, "Pass"])
  tree_pred <- ifelse(tree_score >= 0.5, "Pass", "Fail")
  tree_eval <- evaluate_binary(split$test$Result, tree_pred, tree_score)

  eval_x_train <- split$train[, c("StudyHours", "Attendance", "PreviousMarks")]
  eval_x_test <- split$test[, c("StudyHours", "Attendance", "PreviousMarks")]
  eval_lm <- stats::lm(as.numeric(split$train$Result == "Pass") ~ StudyHours + Attendance + PreviousMarks,
                       data=split$train)
  lm_score <- pmin(1, pmax(0, as.numeric(stats::predict(eval_lm, newdata=eval_x_test))))
  lm_pred <- ifelse(lm_score >= 0.5, "Pass", "Fail")
  lm_eval <- evaluate_binary(split$test$Result, lm_pred, lm_score)

  # 1) Decision Tree classifier (existing API-compatible export) (existing API-compatible export)
  tree <- rpart::rpart(Result ~ StudyHours + Attendance + PreviousMarks,
                       data=students, method="class", control=rpart::rpart.control(cp=0.01))
  export_tree_meta(tree, students, CONFIG$output_dir, CONFIG$tree_filename)

  # 2) Linear probability regression: Pass=1, Fail=0. This estimates a numeric pass score,
  # not a final exam mark. Clamp inference output to [0, 1].
  x <- students[, c("StudyHours", "Attendance", "PreviousMarks")]
  y <- as.numeric(students$Result == "Pass")
  regression <- stats::lm(y ~ StudyHours + Attendance + PreviousMarks, data=students)
  co <- stats::coef(regression)
  reg_payload <- list(
    metadata=list(name="Linear Regression", framework="R stats::lm (linear probability model)",
                  trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
                  total_records=nrow(students), target="Pass=1, Fail=0",
                  target_note="Estimated pass score from binary labels; not a predicted exam mark.",
                  r_squared=unname(summary(regression)$r.squared),
                  rmse=sqrt(mean((stats::predict(regression, students)-y)^2))),
    weights=list(intercept=unname(co[1]), study_hours=unname(co["StudyHours"]),
                 attendance=unname(co["Attendance"]), previous_marks=unname(co["PreviousMarks"]))
  )
  jsonlite::write_json(reg_payload, file.path(CONFIG$output_dir, CONFIG$regression_filename),
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
    loading_names=rownames(pca$rotation), scores=unname(pca$x[, 1:min(3,ncol(pca$x)), drop=FALSE]),
    score_columns=paste0("PC", seq_len(min(3,ncol(pca$x))))
  )
  jsonlite::write_json(pca_payload, file.path(CONFIG$output_dir, CONFIG$pca_filename),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)

  # 4) K-Means on standardized inputs. Fix seed for repeatable demo clusters.
  set.seed(CONFIG$cluster_seed)
  k <- min(CONFIG$clusters, max(2, floor(sqrt(nrow(students)/2))))
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
    dataset_note="Synthetic demo dataset. Decision Tree and Linear Regression validation metrics use a reproducible stratified 80/20 hold-out. Final artifacts are then refit on all rows. PCA and K-Means are descriptive/unsupervised and have no predictive accuracy score.",
    data_source="r_analytics/data/student_data.csv (synthetic demo data)",
    trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"), total_records=nrow(students),
    validation=list(method="stratified 80/20 hold-out", seed=split$seed,
                    train_rows=split$train_rows, test_rows=split$test_rows,
                    positive_class="Pass", threshold=0.5,
                    decision_tree=tree_eval, linear_regression=lm_eval,
                    unsupervised_note="PCA and K-Means are not evaluated as Pass/Fail classifiers; no accuracy, F1 or AUC is assigned to them."),
    result_counts=as.list(table(students$Result)),
    feature_summary=lapply(x, function(v) list(min=min(v), max=max(v), mean=mean(v), median=median(v), sd=stats::sd(v))),
    tree=list(accuracy=mean(stats::predict(tree, students, type="class")==students$Result),
              variable_importance=if (is.null(tree$variable.importance)) list() else as.list(tree$variable.importance)),
    regression=reg_payload$metadata,
    pca=pca_payload$metadata,
    clustering=km$size
  )
  jsonlite::write_json(analytics, file.path(CONFIG$output_dir, CONFIG$analytics_filename),
                       auto_unbox=TRUE, pretty=TRUE, digits=NA)
  cat("Trained and exported Decision Tree, Linear Regression, PCA, K-Means and analytics artifacts.\n")
}
main()
