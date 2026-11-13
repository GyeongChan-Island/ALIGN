#include <Wire.h>
#include <math.h>

#define MPU1_ADDR 0x68   // 흉추
#define MPU2_ADDR 0x69   // 요추
#define SAMPLE_US 10000  // 10ms = 100Hz
#define DT 0.01f         // 샘플 간격(초)
#define ALPHA 0.98f      // 자이로 신뢰 비율

struct Imu {
  uint8_t addr;
  float gBiasX, gBiasY, gBiasZ;   // 자이로 바이어스 (°/s)
  float roll, pitch;              // 상보 필터 결과 각도 (°)
  float accRoll, accPitch;        // 가속도만으로 구한 각도 (비교용)
};

Imu imu1 = {MPU1_ADDR};
Imu imu2 = {MPU2_ADDR};

void writeReg(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool initMPU(uint8_t addr) {
  writeReg(addr, 0x6B, 0x00);   // 슬립 해제
  writeReg(addr, 0x1A, 0x03);   // DLPF 약 44Hz
  writeReg(addr, 0x1B, 0x00);   // 자이로 ±250°/s
  writeReg(addr, 0x1C, 0x00);   // 가속도 ±2g
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool readMPU(uint8_t addr, float &ax, float &ay, float &az,
             float &gx, float &gy, float &gz) {
  Wire.beginTransmission(addr);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(addr, (uint8_t)14) != 14) return false;

  int16_t rAX = (Wire.read() << 8) | Wire.read();
  int16_t rAY = (Wire.read() << 8) | Wire.read();
  int16_t rAZ = (Wire.read() << 8) | Wire.read();
  Wire.read(); Wire.read();
  int16_t rGX = (Wire.read() << 8) | Wire.read();
  int16_t rGY = (Wire.read() << 8) | Wire.read();
  int16_t rGZ = (Wire.read() << 8) | Wire.read();

  ax = rAX / 16384.0;  ay = rAY / 16384.0;  az = rAZ / 16384.0;
  gx = rGX / 131.0;    gy = rGY / 131.0;    gz = rGZ / 131.0;
  return true;
}

void calibrateGyro(Imu &m, int n) {
  float ax, ay, az, gx, gy, gz;
  double sx = 0, sy = 0, sz = 0;
  int ok = 0;
  for (int i = 0; i < n; i++) {
    if (readMPU(m.addr, ax, ay, az, gx, gy, gz)) {
      sx += gx; sy += gy; sz += gz; ok++;
    }
    delay(2);
  }
  if (ok == 0) { Serial.println("Calibration FAILED (no data)"); return; }
  m.gBiasX = sx / ok;  m.gBiasY = sy / ok;  m.gBiasZ = sz / ok;
}

// 가속도(중력 방향)로 기울기 계산
void accelAngles(float ax, float ay, float az, float &roll, float &pitch) {
  roll  = atan2(ay, az) * 180.0 / PI;
  pitch = atan2(-ax, sqrt(ay * ay + az * az)) * 180.0 / PI;
}

// 센서 하나 업데이트: 읽기 → 바이어스 제거 → 상보 필터
bool updateImu(Imu &m) {
  float ax, ay, az, gx, gy, gz;
  if (!readMPU(m.addr, ax, ay, az, gx, gy, gz)) return false;

  gx -= m.gBiasX;  gy -= m.gBiasY;

  accelAngles(ax, ay, az, m.accRoll, m.accPitch);
  m.roll  = ALPHA * (m.roll  + gx * DT) + (1 - ALPHA) * m.accRoll;
  m.pitch = ALPHA * (m.pitch + gy * DT) + (1 - ALPHA) * m.accPitch;
  return true;
}

// 시작 각도를 가속도 값으로 맞춤 (0°에서 시작하면 수렴까지 몇 초 걸림)
void initAngles(Imu &m) {
  float ax, ay, az, gx, gy, gz;
  if (readMPU(m.addr, ax, ay, az, gx, gy, gz)) {
    accelAngles(ax, ay, az, m.roll, m.pitch);
  }
}

void printImu(const char *name, Imu &m) {
  Serial.printf("[%s] Roll: %6.1f (acc %6.1f) | Pitch: %6.1f (acc %6.1f)\n",
                name, m.roll, m.accRoll, m.pitch, m.accPitch);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(400000);
  delay(1000);

  Serial.println(initMPU(imu1.addr) ? "IMU 1 connected! (0x68)" : "IMU 1 connection FAILED!");
  Serial.println(initMPU(imu2.addr) ? "IMU 2 connected! (0x69)" : "IMU 2 connection FAILED!");

  Serial.println("Calibrating... 센서를 움직이지 마세요");
  delay(500);
  calibrateGyro(imu1, 1000);
  calibrateGyro(imu2, 1000);
  Serial.printf("IMU1 bias: %.3f, %.3f, %.3f\n", imu1.gBiasX, imu1.gBiasY, imu1.gBiasZ);
  Serial.printf("IMU2 bias: %.3f, %.3f, %.3f\n", imu2.gBiasX, imu2.gBiasY, imu2.gBiasZ);

  initAngles(imu1);
  initAngles(imu2);
  Serial.println("----------------------------");
}

void loop() {
  static uint32_t last = micros();
  static int count = 0;
  if (micros() - last < SAMPLE_US) return;
  last += SAMPLE_US;

  bool ok1 = updateImu(imu1);
  bool ok2 = updateImu(imu2);

  if (++count < 50) return;   // 0.5초마다 출력
  count = 0;

  if (ok1) printImu("IMU 1", imu1); else Serial.println("[IMU 1] Read failed!");
  if (ok2) printImu("IMU 2", imu2); else Serial.println("[IMU 2] Read failed!");
  Serial.println("----------------------------");
}
