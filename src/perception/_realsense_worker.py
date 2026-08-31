"""Python 3.8-compatible RealSense capture worker used by realsense_bridge."""

import argparse
import json
import math
import sys
import time


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial")
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--frame-timeout-ms", type=int, required=True)
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--max-distance-m", type=float)
    return parser.parse_args()


def send(message):
    print(json.dumps(message, ensure_ascii=True), flush=True)


def confidence(score):
    if score >= 0:
        return 1.0 / (1.0 + math.exp(-score))
    exp_score = math.exp(score)
    return exp_score / (1.0 + exp_score)


class Detector:
    def __init__(self, args):
        import cv2
        import numpy
        import pyrealsense2 as rs

        self.args = args
        self.cv2 = cv2
        self.numpy = numpy
        self.rs = rs
        self.pipeline = rs.pipeline()
        config = rs.config()
        if args.serial:
            config.enable_device(args.serial)
        config.enable_stream(
            rs.stream.depth,
            args.width,
            args.height,
            rs.format.z16,
            args.fps,
        )
        config.enable_stream(
            rs.stream.color,
            args.width,
            args.height,
            rs.format.bgr8,
            args.fps,
        )

        self.started = False
        try:
            self.pipeline.start(config)
            self.started = True
            self.align = rs.align(rs.stream.color)
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception:
            self.close()
            raise

    def capture(self):
        frames = self.pipeline.wait_for_frames(self.args.frame_timeout_ms)
        aligned_frames = self.align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()
        if not color_frame or not depth_frame:
            raise RuntimeError("D435i returned an incomplete frame set")

        image = self.numpy.asanyarray(color_frame.get_data())
        rectangles, scores = self.hog.detectMultiScale(
            image,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )
        accepted_scores = []
        distances = []
        width = color_frame.get_width()
        height = color_frame.get_height()
        for rectangle, score_value in zip(rectangles, scores):
            score = float(score_value)
            if score < self.args.min_score or len(rectangle) < 4:
                continue
            x = int(rectangle[0])
            y = int(rectangle[1])
            box_width = int(rectangle[2])
            box_height = int(rectangle[3])
            center_x = min(max(x + box_width // 2, 0), width - 1)
            center_y = min(max(y + box_height // 2, 0), height - 1)
            distance = float(depth_frame.get_distance(center_x, center_y))
            if distance > 0:
                if (
                    self.args.max_distance_m is not None
                    and distance > self.args.max_distance_m
                ):
                    continue
                distances.append(distance)
            accepted_scores.append(score)

        return {
            "observed_at_s": time.monotonic(),
            "person_count": len(accepted_scores),
            "nearest_person_distance_m": min(distances) if distances else None,
            "confidence": (
                confidence(max(accepted_scores)) if accepted_scores else None
            ),
            "source": "realsense:%s" % (self.args.serial or "D435i"),
        }

    def close(self):
        if self.started:
            self.started = False
            self.pipeline.stop()


def main():
    detector = None
    try:
        detector = Detector(parse_args())
        send({"type": "ready"})
        for line in sys.stdin:
            try:
                request = json.loads(line)
                command = request.get("command")
                if command == "capture":
                    send({"type": "observation", "result": detector.capture()})
                elif command == "close":
                    detector.close()
                    send({"type": "closed"})
                    return 0
                else:
                    send({"type": "error", "message": "unknown worker command"})
            except Exception as exc:  # noqa: BLE001
                send({"type": "error", "message": f"D435i capture failed: {exc}"})
    except Exception as exc:  # noqa: BLE001
        send({"type": "error", "message": f"failed to open RealSense D435i: {exc}"})
        return 1
    finally:
        if detector is not None:
            try:
                detector.close()
            except Exception:  # noqa: BLE001, S110
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
