"""Python 3.8-compatible persistent SmolVLM2 CUDA inference worker."""

import argparse
import base64
import io
import json
import signal
import sys
import time
import warnings

warnings.filterwarnings("ignore", message="Failed to load image Python extension.*")
warnings.filterwarnings("ignore", message="The torchvision.datapoints.*")
warnings.filterwarnings("ignore", message="The torchvision.transforms.v2.*")
signal.signal(signal.SIGINT, signal.SIG_IGN)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    return parser.parse_args()


def send(message):
    print(json.dumps(message, ensure_ascii=True), flush=True)


def build_video_prompt(prompt, frame_count):
    lines = [
        (
            f"User: The following are {frame_count} time-ordered frames from "
            "the robot's most recent video window."
        )
    ]
    for index in range(frame_count):
        lines.extend((f"Frame {index + 1}:", "<image>"))
    lines.extend(
        (
            prompt,
            "Return one compact JSON object without Markdown.",
            "<end_of_utterance>",
            "Assistant:",
        )
    )
    return "\n".join(lines)


class CudaModel:
    def __init__(self, args):
        import torch
        import transformers
        from PIL import Image

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable in the vision worker")
        started = time.monotonic()
        self.torch = torch
        self.image_class = Image
        self.max_new_tokens = args.max_new_tokens
        self.processor = transformers.AutoProcessor.from_pretrained(
            args.model,
            use_fast=False,
            local_files_only=True,
        )
        self.model = transformers.AutoModelForImageTextToText.from_pretrained(
            args.model,
            torch_dtype=torch.float16,
            local_files_only=True,
        ).to("cuda").eval()
        torch.cuda.synchronize()
        self.backend = {
            "device": str(next(self.model.parameters()).device),
            "dtype": str(next(self.model.parameters()).dtype),
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "model": args.model,
            "load_s": round(time.monotonic() - started, 3),
            "allocated_mb": round(torch.cuda.memory_allocated() / 1048576, 1),
        }

    def invoke(self, encoded_frames, prompt):
        images = []
        for encoded in encoded_frames:
            image = self.image_class.open(
                io.BytesIO(base64.b64decode(encoded))
            ).convert("RGB")
            images.append(image)
        model_prompt = build_video_prompt(prompt, len(images))
        inputs = self.processor(
            text=model_prompt,
            videos=images,
            return_tensors="pt",
        ).to("cuda")
        inputs["pixel_values"] = inputs["pixel_values"].to(
            dtype=self.torch.float16
        )
        started = time.monotonic()
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )
        self.torch.cuda.synchronize()
        input_length = inputs["input_ids"].shape[1]
        output = self.processor.batch_decode(
            generated[:, input_length:],
            skip_special_tokens=True,
        )
        if not output:
            raise RuntimeError("SmolVLM2 returned no text")
        return output[0].strip(), {
            "inference_s": round(time.monotonic() - started, 3),
            "frame_count": len(images),
            "peak_mb": round(
                self.torch.cuda.max_memory_allocated() / 1048576,
                1,
            ),
        }


def main():
    model = None
    try:
        model = CudaModel(parse_args())
        send({"type": "ready", "backend": model.backend})
        for line in sys.stdin:
            request = {}
            try:
                request = json.loads(line)
                command = request.get("command")
                if command == "invoke":
                    request_id = request.get("request_id")
                    frames = request.get("frames")
                    prompt = request.get("prompt")
                    if not isinstance(frames, list) or not frames:
                        raise ValueError("invoke requires a non-empty frame list")
                    if not isinstance(prompt, str) or not prompt.strip():
                        raise ValueError("invoke requires a prompt")
                    output, metrics = model.invoke(frames, prompt)
                    send(
                        {
                            "type": "result",
                            "request_id": request_id,
                            "output": output,
                            "metrics": metrics,
                        }
                    )
                elif command == "close":
                    send({"type": "closed"})
                    return 0
                else:
                    send({"type": "error", "message": "unknown worker command"})
            except Exception as exc:  # noqa: BLE001 - isolate request failures
                send(
                    {
                        "type": "error",
                        "request_id": request.get("request_id"),
                        "message": f"CUDA inference failed: {exc}",
                    }
                )
    except Exception as exc:  # noqa: BLE001 - report startup failure to parent
        send({"type": "error", "message": f"failed to load CUDA VLM: {exc}"})
        return 1
    finally:
        model = None
    return 0


if __name__ == "__main__":
    sys.exit(main())
