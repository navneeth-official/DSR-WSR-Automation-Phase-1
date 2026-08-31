"""Pipeline adapter: vision layout inspection via ``app.vision.VisionClient``."""



from __future__ import annotations



import tempfile

from pathlib import Path

from typing import Callable



from app.pipeline.types import RenderBatch, RenderedSlide, VisionReport

from app.services.ppt_format_vision_evaluator import evaluate_deck_vision

from app.vision import VisionClient, VisionClientConfig

from app.vision.logging import configure_vision_logging, default_log_path





class VisionLayoutInspectorClient:

    """

    Pipeline-facing vision client.



    Evaluates each rendered slide image through ``app.vision.VisionClient``

    (GPT-4o by default) and assembles a deck-level ``VisionReport``.

    """



    def __init__(

        self,

        *,

        vision_client: VisionClient | None = None,

        evaluate_deck_fn: Callable[..., dict] | None = None,

        rulebook_path: Path | None = None,

        model: str = "gpt-4o",

    ) -> None:

        self._evaluate_deck_fn = evaluate_deck_fn or evaluate_deck_vision

        self._rulebook_path = rulebook_path

        self._model = model

        self._vision_client = vision_client



    def _get_client(self, log_near: Path | None = None) -> VisionClient:

        if self._vision_client is not None:

            return self._vision_client

        log_path = default_log_path(log_near) if log_near else default_log_path()

        configure_vision_logging(log_path=log_path)

        return VisionClient(

            config=VisionClientConfig(

                model=self._model,

                log_path=log_path,

                json_max_attempts=2,

            ),

        )



    def evaluate(self, render_batch: RenderBatch) -> VisionReport:

        if not render_batch.slides:

            raw = self._evaluate_deck_fn(

                render_batch.ppt_path,

                images_dir=None,

                keep_images=False,

                rulebook_path=self._rulebook_path,

                vision_client=self._get_client(render_batch.ppt_path),

            )

            return VisionReport.from_dict(raw)



        return self._evaluate_render_batch(render_batch)



    def _evaluate_render_batch(self, render_batch: RenderBatch) -> VisionReport:

        client = self._get_client(render_batch.ppt_path)

        reexport_dir: list[Path | None] = [None]

        slide_results: list[dict] = []

        exported_images: list[dict] = []



        for slide in render_batch.slides:

            image_path = self._resolve_slide_image(slide, render_batch, reexport_dir)

            exported_images.append(

                {

                    "slide_index": slide.slide_index,

                    "title": slide.title,

                    "image_path": str(image_path),

                }

            )



            result = client.evaluate(

                image_path,

                slide_number=slide.slide_index,

                context={"title": slide.title},

            )

            record = result.to_dict()

            record["slide_index"] = slide.slide_index

            record["title"] = slide.title

            slide_results.append(record)



        deck_pass = bool(slide_results) and all(s.get("pass") for s in slide_results)

        deck_score = (

            round(sum(s.get("score", 0) for s in slide_results) / len(slide_results))

            if slide_results

            else 0

        )

        critical_issues = [

            f"Slide {s['slide_index']}: {i['issue_id']} — {i['explanation']}"

            for s in slide_results

            for i in s.get("issues", [])

            if i.get("severity") == "high"

        ]

        needs_adjustment = sum(

            1 for s in slide_results if s.get("status") == "needs_adjustment"

        )



        raw = {

            "deck_pass": deck_pass,

            "deck_score": deck_score,

            "slides": slide_results,

            "summary": (

                f"Vision layout inspection: {len(slide_results)} slide(s) evaluated "

                f"with {client.model_name}; {needs_adjustment} need adjustment."

            ),

            "critical_issues": critical_issues,

            "source_file": render_batch.ppt_path.name,

            "evaluator": "vision_layout_inspector",

            "vision_model": client.model_name,

            "images_dir": str(reexport_dir[0] or render_batch.output_dir),

            "exported_images": exported_images,

        }

        return VisionReport.from_dict(raw)



    def _resolve_slide_image(

        self,

        slide: RenderedSlide,

        render_batch: RenderBatch,

        reexport_dir: list[Path | None],

    ) -> Path:

        """

        Return a readable PNG path for the slide.



        When the renderer deleted temp files (keep_images=False), re-export the

        slide on demand so vision evaluation can still run.

        """

        if slide.image_path.is_file():

            return slide.image_path.resolve()



        from app.services.ppt_slide_images import export_slides_to_png



        if reexport_dir[0] is None:

            reexport_dir[0] = Path(

                tempfile.mkdtemp(

                    prefix="ppt_vision_eval_",

                    dir=render_batch.ppt_path.parent,

                )

            )



        exported = export_slides_to_png(

            render_batch.ppt_path,

            reexport_dir[0],

            slide_indices=[slide.slide_index],

        )

        if not exported:

            raise FileNotFoundError(

                f"Could not export slide {slide.slide_index} from "

                f"{render_batch.ppt_path}"

            )

        return Path(exported[0]["image_path"]).resolve()



    def passes(self, report: VisionReport) -> bool:

        return report.deck_pass

