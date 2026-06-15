  # PiCar-X Autonomous Navigation Challenge 🚗💨
  
  An autonomous vehicle project for a 4-day hackathon. The objective is to program the SunFounder PiCar-X to autonomously navigate a mimicked road track and respond correctly to traffic signs using Computer Vision and fallback hardware sensors.
  
---
## 🌿 Git Branching & Workflow Rules

To prevent code overrides and messy merge conflicts, we use a strict **3-tier branch structure**:

* **🟢 1. main branch (Production Code)**
  * *Only bug-free, track-tested code lives here. Direct pushes are blocked.*
  * └── **🟠 2. develop branch (Integration Sandbox)**
    * *Where pairs open PRs to combine and test their logic together.*
    * ├── **🔵 feature/lane-hsv** (Pair B Workspace)
    * ├── **🔵 feature/picar-motion** (Pair A Workspace)
    * └── **🔵 feature/sign-contours** (Pair C Workspace)

### 🚨 The 3 Rules of Engagement:
1. **Never work on `main` or `develop` directly.** Always spin up a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature-name
