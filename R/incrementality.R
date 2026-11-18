# Independent R check of the main incrementality results.
# Run from the repo root:  Rscript R/incrementality.R
# Uses base R only (stats package), so no installs are needed.

df <- read.csv("data/hillstrom.csv", stringsAsFactors = FALSE)
stopifnot(nrow(df) == 64000)

control <- df[df$segment == "No E-Mail", ]
out <- data.frame()

for (camp in c("Mens E-Mail", "Womens E-Mail")) {
  t <- df[df$segment == camp, ]
  for (m in c("visit", "conversion")) {
    pt <- prop.test(c(sum(t[[m]]), sum(control[[m]])), c(nrow(t), nrow(control)), correct = FALSE)
    out <- rbind(out, data.frame(campaign = camp, metric = m,
      diff = unname(pt$estimate[1] - pt$estimate[2]),
      ci_low = pt$conf.int[1], ci_high = pt$conf.int[2], p_value = pt$p.value))
  }
  tt <- t.test(t$spend, control$spend, var.equal = FALSE)
  out <- rbind(out, data.frame(campaign = camp, metric = "spend",
    diff = unname(tt$estimate[1] - tt$estimate[2]),
    ci_low = tt$conf.int[1], ci_high = tt$conf.int[2], p_value = tt$p.value))
}
out$p_holm <- p.adjust(out$p_value, method = "holm")

# Does the Womens email only work on past womens-category buyers?
w <- df[df$segment %in% c("Womens E-Mail", "No E-Mail"), ]
w$treated <- as.integer(w$segment == "Womens E-Mail")
fit <- glm(visit ~ treated * womens, data = w, family = binomial())
interaction_p <- summary(fit)$coefficients["treated:womens", "Pr(>|z|)"]

dir.create("output", showWarnings = FALSE)
write.csv(out, "output/r_ate.csv", row.names = FALSE)
writeLines(format(interaction_p, digits = 6), "output/r_interaction_p.txt")
print(out, digits = 4)
cat("Interaction p-value (treated x womens):", format(interaction_p, digits = 4), "\n")
