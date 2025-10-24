## 0.9.0 (2025-10-24)

### Enhancements

* Replaced deprecated `pkg_resources` with `importlib.resources`. (#391 via #424)
* Add Simple Contribution Guide. (#416 via )

### Bug fixes

* Fix issue with extended path format on Windows. (#398 via #432)
* Fix executables for all users. (#438)

### Other

* Update Python supported versions. (#414 via #417)
* Various dependency updates and CI improvements (#418 via )

### Contributors

* @Dave-Karetnyk-TFS
* @ryanskeith
* @xhochy


# 0.8.1 (2024-11-15)

## What's Changed
* Make gzip-based archives reproducible by @xhochy in https://github.com/conda/conda-pack/pull/349
* Drop support for Python 3.7 by @xhochy in https://github.com/conda/conda-pack/pull/360
* feat: add zstd support by @kelvinou01 in https://github.com/conda/conda-pack/pull/351
* Switch to official gh action for gh-pages by @ericdill in https://github.com/conda/conda-pack/pull/376
* Add the deploy step for gh pages by @ericdill in https://github.com/conda/conda-pack/pull/377
* docs: source file name same as output by @yasir-choudhry in https://github.com/conda/conda-pack/pull/371
* Only deploy docs when release is tagged by @dbast in https://github.com/conda/conda-pack/pull/378

## New Contributors
* @kelvinou01 made their first contribution in https://github.com/conda/conda-pack/pull/351
* @ericdill made their first contribution in https://github.com/conda/conda-pack/pull/376
* @yasir-choudhry made their first contribution in https://github.com/conda/conda-pack/pull/371


# 0.8.0 (2024-06-25)

## What's Changed
* xfail test_format[squashfs] on Mac for Py<3.9 by @xhochy in https://github.com/conda/conda-pack/pull/281
* Fix squashfs packaging when using `--dest-prefix` by @rafiyr in https://github.com/conda/conda-pack/pull/210
* squashfs: Correct root dir permissions consistency by using a subdirectoy by @rafiyr in https://github.com/conda/conda-pack/pull/267
* Upload releases to PyPI using trusted publishing by @xhochy in https://github.com/conda/conda-pack/pull/279
* Remove missing files from the file list. by @xhochy in https://github.com/conda/conda-pack/pull/118
* Create the output directory if its missing and `force` is used, otherwise raise  by @KrishanBhasin in https://github.com/conda/conda-pack/pull/295
* Fix in SquashFSArchive._add #248 by @Kirill888 in https://github.com/conda/conda-pack/pull/306
* Fix crash when using conda-pack on environments created with pixi by @melund in https://github.com/conda/conda-pack/pull/305
* Update parcel.rst by @bkreider in https://github.com/conda/conda-pack/pull/317
* Use `macos-12` runners by @xhochy in https://github.com/conda/conda-pack/pull/333
* Add dependabot.yml by @xhochy in https://github.com/conda/conda-pack/pull/332
* Add no-archive format for fast environment clone by @ayurchuk in https://github.com/conda/conda-pack/pull/320
* activate.fish: support activating conda in fish shells by @d4l3k in https://github.com/conda/conda-pack/pull/342

## New Contributors
* @rafiyr made their first contribution in https://github.com/conda/conda-pack/pull/210
* @KrishanBhasin made their first contribution in https://github.com/conda/conda-pack/pull/295
* @Kirill888 made their first contribution in https://github.com/conda/conda-pack/pull/306
* @melund made their first contribution in https://github.com/conda/conda-pack/pull/305
* @bkreider made their first contribution in https://github.com/conda/conda-pack/pull/317
* @ayurchuk made their first contribution in https://github.com/conda/conda-pack/pull/320
* @d4l3k made their first contribution in https://github.com/conda/conda-pack/pull/342


# 0.7.1 (2023-08-07)

## What's Changed
* Updates tests to Python 3.7/3.10, as 2.7/3.6 being EOL by @dbast in https://github.com/conda/conda-pack/pull/207
* Renovations and require Python >=3.7 by @dbast in https://github.com/conda/conda-pack/pull/206
* document packaging of environments as self-extracting executables by @saraedum in https://github.com/conda/conda-pack/pull/159
* Add fix for core.py missing space by @Rtanti in https://github.com/conda/conda-pack/pull/218
* Re-enable coverage reporting by @dbast in https://github.com/conda/conda-pack/pull/251
* Allow the compression level to be set in zip files by @jjhelmus in https://github.com/conda/conda-pack/pull/252
* Fix path separator on Windows distributions by @andysham in https://github.com/conda/conda-pack/pull/275
* codesign binaries on osx-arm64 by @xhochy in https://github.com/conda/conda-pack/pull/257

## New Contributors
* @saraedum made their first contribution in https://github.com/conda/conda-pack/pull/159
* @Rtanti made their first contribution in https://github.com/conda/conda-pack/pull/218
* @kenodegard made their first contribution in https://github.com/conda/conda-pack/pull/227
* @jezdez made their first contribution in https://github.com/conda/conda-pack/pull/233
* @jjhelmus made their first contribution in https://github.com/conda/conda-pack/pull/252
* @andysham made their first contribution in https://github.com/conda/conda-pack/pull/275
