# Make paths independent of the caller working directory.
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grepl("^--file=", args)][1])
script_dir <- dirname(normalizePath(file_arg, winslash = "/", mustWork = TRUE))
setwd(normalizePath(file.path(script_dir, ".."), winslash = "/", mustWork = TRUE))
source("src/config.R")
source("src/utils.R")

if (!requireNamespace("rpart", quietly = TRUE)) install.packages("rpart", repos="https://cloud.r-project.org")
if (!requireNamespace("jsonlite", quietly = TRUE)) install.packages("jsonlite", repos="https://cloud.r-project.org")

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

  # 1) Decision Tree classifier (existing API-compatible export)
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
    dataset_note="Synthetic demo dataset; metrics below are in-sample descriptive metrics, not held-out validation.",
    trained_at=format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"), total_records=nrow(students),
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
