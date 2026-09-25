source("src/config.R")
source("src/utils.R")

if(!require(rpart)) install.packages("rpart", repos="https://r-project.org")

main <- function() {
  cat("Initializing Cyber-Yellow Classification Model Training Pass...\n")

  if (!file.exists(CONFIG$data_path)) {
    stop(paste("Data file missing at configuration check destination:", CONFIG$data_path))
  }

  students <- read.csv(CONFIG$data_path)
  students$Result <- as.factor(students$Result)

  # Compute tree splits mapping parameters
  model <- rpart(Result ~ StudyHours + Attendance + PreviousMarks, data = students, method = "class")

  export_tree_meta(model, students, CONFIG$output_dir, CONFIG$model_filename)
}

main()
