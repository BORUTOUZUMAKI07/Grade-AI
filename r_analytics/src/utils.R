library(jsonlite)

# Walks an rpart tree into a plain nested list the API can read: at each node,
# go left when the feature is below the threshold, otherwise go right.
# rpart keeps the original column names (StudyHours); the API expects the snake_case
# names used in raw_records (study_hours), so each feature name is translated here.
FEATURE_NAME_MAP <- c(StudyHours = "study_hours", Attendance = "attendance", PreviousMarks = "previous_marks")

build_tree_json <- function(model) {
  frame  <- model$frame
  ids    <- as.integer(rownames(frame))
  leaf   <- frame$var == "<leaf>"
  splits <- model$splits
  lv     <- attr(model, "ylevels")
  split_row <- cumsum(c(1, frame$ncompete + frame$nsurrogate + !leaf))

  build_node <- function(id) {
    i <- match(id, ids)
    if (leaf[i]) {
      counts <- as.integer(frame$yval2[i, 1 + seq_along(lv)])
      return(list(leaf = TRUE, prediction = lv[frame$yval[i]],
                 counts = setNames(as.list(counts), lv), n = frame$n[i]))
    }
    row  <- split_row[i]
    cut  <- unname(splits[row, "index"])
    ncat <- unname(splits[row, "ncat"])
    kids <- list(build_node(2 * id), build_node(2 * id + 1))
    # rpart: ncat < 0 means the left child holds value < cut; ncat > 0 means left holds value >= cut.
    raw_name <- as.character(frame$var[i])
    feature_name <- if (raw_name %in% names(FEATURE_NAME_MAP)) FEATURE_NAME_MAP[[raw_name]] else raw_name
    list(feature = feature_name, threshold = cut,
        left  = if (ncat < 0) kids[[1]] else kids[[2]],
        right = if (ncat < 0) kids[[2]] else kids[[1]])
  }
  build_node(1)
}

export_tree_meta <- function(model, dataset, target_dir, filename) {
  if (!dir.exists(target_dir)) {
    dir.create(target_dir, recursive = TRUE)
  }

  # Format multi-axis coordinate entries array vectors safely
  dataset_list <- lapply(1:nrow(dataset), function(i) {
    list(
      study_hours = as.numeric(dataset$StudyHours[i]),
      attendance = as.numeric(dataset$Attendance[i]),
      previous_marks = as.numeric(dataset$PreviousMarks[i]),
      result = as.character(dataset$Result[i])
    )
  })

  predicted <- predict(model, dataset, type = "class")
  importance <- if (is.null(model$variable.importance)) list() else as.list(round(model$variable.importance, 3))

  payload <- list(
    metadata = list(
      framework = "R base::rpart",
      trained_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%SZ"),
      total_records = nrow(dataset),
      training_accuracy = round(mean(predicted == dataset$Result), 4),
      variable_importance = importance
    ),
    tree = build_tree_json(model),
    raw_records = dataset_list
  )

  out_path <- file.path(target_dir, filename)
  write_json(payload, out_path, auto_unbox = TRUE, pretty = TRUE, digits = NA)
  cat(paste("Successfully exported Decision Tree metadata coordinates to:", out_path, "\n"))
}
