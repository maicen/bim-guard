# Validation and research

> BIM Guard's accuracy claims are scored in a separate public repository and published with their limits: benchmark results, a claims ledger and known gaps.

Compliance software is only useful if you can trust its findings. BIM Guard's evaluation harnesses live in an independent public repository, and results are published together with what they cannot show.

## What the evaluation currently supports

- **22 of 22** architecture-engine benchmark cases classified correctly (13 true positives, 9 true negatives, no false positives or negatives). The cases are few and procedurally generated, so the 95% Wilson confidence interval for accuracy, 85.1% to 100%, matters more than the point estimate.
- **60 of 60** NLP annotation test cases passing, fully reproducible.

## What is not claimed

Some harnesses in the repository simulate their inputs. Their numbers are labelled as such and are not evidence about BIM Guard. Every headline number in the repository is listed in a claims ledger with its producing script, artifact and verification status.

## Read the evidence

- [BIM-Guard Evaluation site](https://maicen.github.io/bim-guard-evaluation/) - overview and legend
- [Results](https://maicen.github.io/bim-guard-evaluation/results.html) - the architecture-engine confusion matrix
- [Claims ledger](https://maicen.github.io/bim-guard-evaluation/claims.html) - every headline number and its evidence
- [Limitations](https://maicen.github.io/bim-guard-evaluation/limitations.html) - methodological gaps, stated plainly
- [Reproduce](https://maicen.github.io/bim-guard-evaluation/reproduce.html) - commands to re-run each harness
- [bim-guard-evaluation on GitHub](https://github.com/maicen/bim-guard-evaluation) - source and citation file
- [bim-guard on GitHub](https://github.com/maicen/bim-guard) - the platform itself

## Related

[Automated IFC compliance checking](/ifc-compliance-checking) · [All features](/features) · [Documentation](/docs)

Canonical page: https://bim-guard.xyz/research
