CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080
CAMERA_FPS = 30
CAMERA_RESOLUTION_FALLBACKS = (
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
    (1280, 720),
    (640, 480),
)
WINDOWS_PREFERRED_CAMERA_INDEX = 1
CAMERA_SCAN_MAX_INDEX = 3

# 1080p30 é o ponto de equilíbrio. O serviço mede estabilidade e FPS antes de
# subir para 1440p/4K e reduz para 720p/480p quando 1080p não estiver confortável.
# A captura continua em até 30 FPS e a interface redesenha em 20 FPS para reduzir
# conversões no Raspberry Pi 3 sem limitar o frame mais recente da inspeção.
FRAME_INTERVAL_MS = 33
PARAMETERIZATION_PREVIEW_INTERVAL_MS = 50
OPERATION_PREVIEW_WIDTH = 480
OPERATION_PREVIEW_HEIGHT = 270
OPERATION_PREVIEW_INTERVAL_MS = 50
OPERATION_RESULT_DISPLAY_MS = 3000
GPIO_TRIGGER_BCM_PIN = 27
GPIO_TRIGGER_BOUNCE_S = 0.08
GPIO_EVENT_POLL_MS = 50
GPIO_POSITIONING_DELAY_MS = 2000
