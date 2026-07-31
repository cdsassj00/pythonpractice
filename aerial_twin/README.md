# aerial_twin — 조감도 기반 3D 사이트 트윈

레퍼런스 조감도(숲으로 둘러싸인 플랜트 캠퍼스)를 **파라메트릭 3D 모델**로 재구성하고
`.glb` / `.gltf`로 내보내는 파이프라인입니다.

## 산출물

| 파일 | 내용 |
|---|---|
| `dist/plant_site.glb` | 단일 바이너리 glTF (약 6 MB, 18개 머티리얼, ~116k 삼각형) |
| `dist/plant_site.gltf` | 동일 모델의 JSON + 임베디드 버퍼 버전 |
| `dist/preview.png` | 레퍼런스와 구도를 맞춘 확인용 프리뷰 |

## 사용법

Blender 없이 바로 GLB 굽기 (`pygltflib` + `numpy`만 필요):

```bash
pip install pygltflib numpy pillow
python3 build_glb.py --gltf              # dist/plant_site.glb + .gltf
python3 build_glb.py --no-forest         # 캠퍼스만, 파일 크기 1/3
python3 preview.py --width 1600 --height 1066
```

Blender에서 같은 레이아웃을 재현 / 렌더 / 재export:

```bash
blender --background --python build_blender.py -- --glb dist/plant_site_blender.glb
blender --background --python build_blender.py -- --render dist/render.png --samples 256
```

`build_blender.py`는 GUI Blender의 Scripting 탭에서 Run 해도 동일하게 씬을 만듭니다.
Cycles 머티리얼과 항공 카메라가 이미 잡혀 있으므로, 수작업 디테일링은 여기서 이어가면 됩니다.

## 구조

```
site_layout.py   ← 유일한 진실 소스. 치수·좌표·머티리얼을 전부 여기서 정의
meshlib.py       ← box / cylinder / cone / gable 프리미티브 → 삼각형
build_glb.py     ← 레이아웃을 머티리얼별 glTF primitive로 병합해 GLB 작성
build_blender.py ← 같은 레이아웃을 Blender 오브젝트로 생성, 렌더/export
preview.py       ← numpy z-buffer 소프트웨어 렌더러 (구도 확인용)
```

좌표계는 **미터, Z-up**, 원점은 담장 안 부지 중심입니다.
glTF는 Y-up이므로 `build_glb.py`가 저장 시점에 `(x, z, -y)`로 변환합니다.

## 재현한 요소

- 부지 340 × 280 m 플랫폼, 담장, 순환도로, 내부 간선도로
- A: 북측 장방형 슬래브동(156 m, 톱날형 루프 모니터 17개, 리본 창)
- B: 북동측 고층 생산동(62 × 58 m, H 31 m)
- C: 중앙 수직 핀 파사드 타워(H 44 m, 최고 볼륨)
- D: 청색 스탠딩심 지붕 홀 / E: 청색 지붕 중층동 / F·G: 서측 저층동
- 탱크팜(대형 탱크 2기 + 사일로 2기 + 스택 H 42 m), 변전 야드, 칠러 뱅크
- 남측 유틸리티동 5동, 정문 게이트·캐노피, 주차장 및 차선 도장
- 잔디 필드, 헤지, 가로수, 외곽 침엽수림 2,400그루, 하부 공도 및 횡단보도

치수는 레퍼런스 하단 공도 폭(약 24 m)을 스케일 기준으로 역산했습니다.
정합도를 더 올리려면 `site_layout.py`의 각 블록 좌표/치수만 수정하면
GLB·Blender 씬·프리뷰가 함께 갱신됩니다.

## 한계

레퍼런스 이미지 한 장에서 복원한 것이므로 가려진 면, 실제 층고, 설비 배관,
파사드 디테일은 추정치입니다. "100% 트윈"이 실측 수준을 뜻한다면 도면이나
추가 각도의 사진이 필요합니다 — 그 경우 여러 뷰를 넣을 수 있는
Higgsfield `multi_image_to_3d` 쪽이 더 유리합니다.
