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
    frame_gaze_offset: list[Optional[float]] = field(default_factory=list)   # iris horizontal offset [-1,1]
    frame_hand_detected: list[int] = field(default_factory=list)
    frame_hand_movement: list[Optional[float]] = field(default_factory=list)
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


# Iris landmark indices (only when refine_landmarks=True):
# 468=right iris center, 473=left iris center
# Eye corners for width estimation:
_RIGHT_EYE_OUTER = 33   # right eye outer corner
_RIGHT_EYE_INNER = 133  # right eye inner corner
_LEFT_EYE_OUTER  = 263  # left eye outer corner
_LEFT_EYE_INNER  = 362  # left eye inner corner


def _gaze_offset(landmarks, n_landmarks: int) -> Optional[float]:
    """Horizontal iris offset relative to eye width. Range ≈ [-1, 1], 0 = centred."""
    if n_landmarks < 478:
        return None
    right_iris = landmarks[468]
    left_iris  = landmarks[473]
    r_outer = landmarks[_RIGHT_EYE_OUTER]
    r_inner = landmarks[_RIGHT_EYE_INNER]
    l_outer = landmarks[_LEFT_EYE_OUTER]
    l_inner = landmarks[_LEFT_EYE_INNER]

    r_center_x = (r_outer.x + r_inner.x) / 2
    r_width    = abs(r_outer.x - r_inner.x)
    l_center_x = (l_outer.x + l_inner.x) / 2
    l_width    = abs(l_outer.x - l_inner.x)

    if r_width < 1e-4 and l_width < 1e-4:
        return None
    r_off = (right_iris.x - r_center_x) / r_width if r_width > 1e-4 else 0.0
    l_off = (left_iris.x  - l_center_x) / l_width  if l_width  > 1e-4 else 0.0
    return float((r_off + l_off) / 2)


def _hand_centroid(hand_lms) -> tuple[float, float]:
    xs = [lm.x for lm in hand_lms]
    ys = [lm.y for lm in hand_lms]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


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
    mp_face  = mp.solutions.face_mesh
    mp_pose  = mp.solutions.pose
    mp_hands = mp.solutions.hands
    prev_pose_lms = None
    prev_hand_centroids: list[tuple[float, float]] = []
    frame_idx = 0

    with (
        mp_face.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,          # enables 478 landmarks (iris)
            min_detection_confidence=0.5,
        ) as face_mesh,
        mp_pose.Pose(
            static_image_mode=True,
            model_complexity=0,
            min_detection_confidence=0.5,
        ) as pose,
        mp_hands.Hands(
            static_image_mode=True,
            max_num_hands=2,
            min_detection_confidence=0.5,
        ) as hands,
    ):
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                timestamp = round(frame_idx / video_fps, 3)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]

                # Face + head pose + iris gaze
                face_res = face_mesh.process(rgb)
                face_detected = 0
                yaw = pitch = roll = None
                gaze = None
                if face_res.multi_face_landmarks:
                    face_detected = 1
                    lms = face_res.multi_face_landmarks[0].landmark
                    yaw, pitch, roll = _head_pose(lms, w, h)
                    gaze = _gaze_offset(lms, len(lms))

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

                # Hands
                hand_res = hands.process(rgb)
                hand_detected = 0
                hand_movement = None
                if hand_res.multi_hand_landmarks:
                    hand_detected = 1
                    cur_centroids = [_hand_centroid(h_lms.landmark)
                                     for h_lms in hand_res.multi_hand_landmarks]
                    if prev_hand_centroids:
                        dists = []
                        for i, cc in enumerate(cur_centroids):
                            if i < len(prev_hand_centroids):
                                pc = prev_hand_centroids[i]
                                dists.append(math.sqrt((cc[0]-pc[0])**2 + (cc[1]-pc[1])**2))
                        if dists:
                            hand_movement = float(np.mean(dists))
                    prev_hand_centroids = cur_centroids
                else:
                    prev_hand_centroids = []

                result.frame_timestamps.append(timestamp)
                result.frame_numbers.append(frame_idx)
                result.frame_face_detected.append(face_detected)
                result.frame_head_yaw.append(round(yaw, 2) if yaw is not None else None)
                result.frame_head_pitch.append(round(pitch, 2) if pitch is not None else None)
                result.frame_head_roll.append(round(roll, 2) if roll is not None else None)
                result.frame_body_movement.append(round(movement, 5) if movement is not None else None)
                result.frame_gaze_offset.append(round(gaze, 4) if gaze is not None else None)
                result.frame_hand_detected.append(hand_detected)
                result.frame_hand_movement.append(round(hand_movement, 5) if hand_movement is not None else None)
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

    # Iris gaze offset (0=centred, ±1=extreme lateral)
    gazes = [g for g in result.frame_gaze_offset if g is not None]
    if gazes:
        metrics.append(("gaze_offset_mean", float(np.mean(gazes)), "ratio", 0.75))
        metrics.append(("gaze_offset_std", float(np.std(gazes)), "ratio", 0.75))
        # fraction of frames where |gaze| < 0.15 (approx. centred)
        centred = [abs(g) < 0.15 for g in gazes]
        metrics.append(("gaze_centred_ratio", sum(centred) / len(centred), "ratio", 0.75))

    # Hand presence and movement
    if result.frame_hand_detected:
        hand_ratio = sum(result.frame_hand_detected) / n
        metrics.append(("hand_visible_ratio", hand_ratio, "ratio", 0.8))
    hand_moves = [m for m in result.frame_hand_movement if m is not None]
    if hand_moves:
        metrics.append(("hand_movement_mean", float(np.mean(hand_moves)), "normalized", 0.8))
        metrics.append(("hand_movement_std", float(np.std(hand_moves)), "normalized", 0.8))

    return metrics
