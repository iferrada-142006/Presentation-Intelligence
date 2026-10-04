"""
Computer vision analysis using MediaPipe.

Observations (measured, never inferred):
- Face presence per sampled frame
- Head orientation: yaw / pitch / roll in degrees via PnP from face landmarks
- Body movement: mean landmark displacement between consecutive sampled frames

What this intentionally does NOT do:
- Emotion recognition
- Biometric identification
- "Confidence" or psychological inference
- Eye contact → engagement inference (we measure head direction only)

Sampling at ~2 fps is sufficient for presentation-scale analysis (head turns,
posture shifts) without spending CPU on sub-second micro-movements.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_FPS = 2.0

# Generic 3D face model reference points (mm, nose-tip origin)
_FACE_3D = np.array([
    [  0.0,    0.0,    0.0],   # Nose tip         (landmark 4)
    [  0.0, -330.0,  -65.0],   # Chin             (landmark 152)
    [-225.0,  170.0, -135.0],  # Left eye corner  (landmark 263)
    [ 225.0,  170.0, -135.0],  # Right eye corner (landmark 33)
    [-150.0, -150.0, -125.0],  # Left mouth       (landmark 287)
    [ 150.0, -150.0, -125.0],  # Right mouth      (landmark 57)
], dtype=np.float64)

_FACE_LM_IDS = [4, 152, 263, 33, 287, 57]
_BODY_LM_IDS = [11, 12, 23, 24]  # left/right shoulder, left/right hip


@dataclass
class VisionAnalysisResult:
    frame_timestamps: list[float] = field(default_factory=list)
    frame_numbers: list[int] = field(default_factory=list)
    frame_face_detected: list[int] = field(default_factory=list)
    frame_head_yaw: list[Optional[float]] = field(default_factory=list)
    frame_head_pitch: list[Optional[float]] = field(default_factory=list)
    frame_head_roll: list[Optional[float]] = field(default_factory=list)
    frame_body_movement: list[Optional[float]] = field(default_factory=list)
    total_frames_sampled: int = 0


def _head_pose(
    landmarks, w: int, h: int
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    img_pts = np.array(
        [[landmarks[i].x * w, landmarks[i].y * h] for i in _FACE_LM_IDS],
        dtype=np.float64,
    )
    focal = float(w)
    cam_matrix = np.array(
        [[focal, 0, w / 2], [0, focal, h / 2], [0, 0, 1]], dtype=np.float64
    )
    ok, rvec, _ = cv2.solvePnP(
        _FACE_3D, img_pts, cam_matrix, np.zeros((4, 1)), flags=cv2.SOLVEPNP_ITERATIVE
    )
    if not ok:
        return None, None, None

    rmat, _ = cv2.Rodrigues(rvec)
    sy = math.sqrt(rmat[0, 0] ** 2 + rmat[1, 0] ** 2)
    if sy > 1e-6:
        roll  = math.atan2(rmat[2, 1], rmat[2, 2])
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw   = math.atan2(rmat[1, 0], rmat[0, 0])
    else:
        roll  = math.atan2(-rmat[1, 2], rmat[1, 1])
        pitch = math.atan2(-rmat[2, 0], sy)
        yaw   = 0.0
    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def _body_movement(cur_lms, prev_lms) -> Optional[float]:
    if prev_lms is None:
        return None
    disps = []
    for idx in _BODY_LM_IDS:
        c, p = cur_lms[idx], prev_lms[idx]
        if c.visibility > 0.4 and p.visibility > 0.4:
            disps.append(math.sqrt((c.x - p.x) ** 2 + (c.y - p.y) ** 2))
    return float(np.mean(disps)) if disps else None


def analyze(video_path: str, sample_fps: float = SAMPLE_FPS) -> VisionAnalysisResult:
    """
    Process a video file and return per-frame measurements.
    Returns an empty result if mediapipe is unavailable or the video can't be opened.
    """
    try:
        import mediapipe as mp
    except ImportError:
        logger.warning("mediapipe not installed — skipping vision stage")
        return VisionAnalysisResult()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Cannot open video: {video_path}")
        return VisionAnalysisResult()

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(video_fps / sample_fps))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info(
        f"Vision: {video_path} fps={video_fps:.1f} interval={frame_interval} "
        f"~{total_frames // frame_interval} samples expected"
    )

    result = VisionAnalysisResult()
    mp_face = mp.solutions.face_mesh
    mp_pose = mp.solutions.pose
    prev_pose_lms = None
    frame_idx = 0

    with (
        mp_face.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
        ) as face_mesh,
        mp_pose.Pose(
            static_image_mode=True,
            model_complexity=0,
            min_detection_confidence=0.5,
        ) as pose,
    ):
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 3)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]

                # Face + head pose
                face_res = face_mesh.process(rgb)
                face_detected = 0
                yaw = pitch = roll = None
                if face_res.multi_face_landmarks:
                    face_detected = 1
                    lms = face_res.multi_face_landmarks[0].landmark
                    yaw, pitch, roll = _head_pose(lms, w, h)

                # Body pose + movement
                pose_res = pose.process(rgb)
                movement = None
                if pose_res.pose_landmarks:
                    movement = _body_movement(
                        pose_res.pose_landmarks.landmark, prev_pose_lms
                    )
                    prev_pose_lms = pose_res.pose_landmarks.landmark
                else:
                    prev_pose_lms = None

                result.frame_timestamps.append(timestamp)
                result.frame_numbers.append(frame_idx)
                result.frame_face_detected.append(face_detected)
                result.frame_head_yaw.append(round(yaw, 2) if yaw is not None else None)
                result.frame_head_pitch.append(round(pitch, 2) if pitch is not None else None)
                result.frame_head_roll.append(round(roll, 2) if roll is not None else None)
                result.frame_body_movement.append(
                    round(movement, 5) if movement is not None else None
                )
                result.total_frames_sampled += 1

            frame_idx += 1

    cap.release()
    logger.info(f"Vision: completed {result.total_frames_sampled} sampled frames")
    return result


def compute_vision_metrics(result: VisionAnalysisResult) -> list[tuple]:
    """Returns list of (metric_name, value, unit, confidence)."""
    if result.total_frames_sampled == 0:
        return []

    metrics = []
    n = result.total_frames_sampled

    # Face presence
    face_ratio = sum(result.frame_face_detected) / n
    metrics.append(("face_visible_ratio", face_ratio, "ratio", 0.9))

    # Head orientation statistics (frames where face was detected)
    yaws = [y for y in result.frame_head_yaw if y is not None]
    pitches = [p for p in result.frame_head_pitch if p is not None]

    if yaws:
        metrics.append(("head_yaw_mean", float(np.mean(yaws)), "degrees", 0.8))
        metrics.append(("head_yaw_std", float(np.std(yaws)), "degrees", 0.8))

    if pitches:
        metrics.append(("head_pitch_mean", float(np.mean(pitches)), "degrees", 0.8))
        metrics.append(("head_pitch_std", float(np.std(pitches)), "degrees", 0.8))

    # Head-forward ratio: fraction of frames where head is roughly facing camera
    # (|yaw| < 20° AND |pitch| < 20°) — observable proxy for camera orientation
    if yaws and pitches:
        forward = [
            abs(y) < 20.0 and abs(p) < 20.0
            for y, p in zip(result.frame_head_yaw, result.frame_head_pitch)
            if y is not None and p is not None
        ]
        if forward:
            metrics.append(("head_forward_ratio", sum(forward) / len(forward), "ratio", 0.75))

    # Body movement
    movements = [m for m in result.frame_body_movement if m is not None]
    if movements:
        metrics.append(("body_movement_mean", float(np.mean(movements)), "normalized", 0.8))
        metrics.append(("body_movement_std", float(np.std(movements)), "normalized", 0.8))

    return metrics
