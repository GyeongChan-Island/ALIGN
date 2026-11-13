#include <Wire.h>

#define MPU1_ADDR 0x68   // 흉추
#define MPU2_ADDR 0x69   // 요추
#define SAMPLE_US 10000  // 10ms = 100Hz

struct Imu {
  uint8_t addr;
  float gBiasX, gBiasY, gBiasZ;   // 자이로 바이어스 (°/s)
};

Imu imu1 = {MPU1_ADDR, 0, 0, 0};
Imu imu2 = {MPU2_ADDR, 0, 0, 0};

void writeReg(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool initMPU(uint8_t addr) {
  writeReg(addr, 0x6B, 0x00);   // PWR_MGMT_1: 슬립 해제
  writeReg(addr, 0x1A, 0x03);   // CONFIG: DLPF 약 44Hz
  writeReg(addr, 0x1B, 0x00);   // GYRO_CONFIG: ±250°/s (131 LSB/°/s)
  writeReg(addr, 0x1C, 0x00);   // ACCEL_CONFIG: ±2g (16384 LSB/g)
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
  Wire.read(); Wire.read();                       // 온도는 건너뜀
  int16_t rGX = (Wire.read() << 8) | Wire.read();
  int16_t rGY = (Wire.read() << 8) | Wire.read();
  int16_t rGZ = (Wire.read() << 8) | Wire.read();

  ax = rAX / 16384.0;  ay = rAY / 16384.0;  az = rAZ / 16384.0;
  gx = rGX / 131.0;    gy = rGY / 131.0;    gz = rGZ / 131.0;
  return true;
}

// 정지 상태에서 N번 읽어 평균 = 바이어스
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

void printImu(const char *name, float ax, float ay, float az,
              float gx, float gy, float gz) {
  Serial.printf("[%s] Accel: %.2f, %.2f, %.2f | Gyro: %.2f, %.2f, %.2f\n",
                name, ax, ay, az, gx, gy, gz);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(400000);          // 400kHz: 센서 2개를 100Hz로 읽기에 여유
  delay(1000);

  Serial.println(initMPU(imu1.addr) ? "IMU 1 connected! (0x68)" : "IMU 1 connection FAILED!");
  Serial.println(initMPU(imu2.addr) ? "IMU 2 connected! (0x69)" : "IMU 2 connection FAILED!");

  Serial.println("Calibrating... 센서를 움직이지 마세요");
  delay(500);
  calibrateGyro(imu1, 1000);
  calibrateGyro(imu2, 1000);

  Serial.printf("IMU1 bias: %.3f, %.3f, %.3f\n", imu1.gBiasX, imu1.gBiasY, imu1.gBiasZ);
  Serial.printf("IMU2 bias: %.3f, %.3f, %.3f\n", imu2.gBiasX, imu2.gBiasY, imu2.gBiasZ);
  Serial.println("----------------------------");
}

void loop() {
  static uint32_t last = micros();
  static int count = 0;
  if (micros() - last < SAMPLE_US) return;   // 100Hz로 읽기
  last += SAMPLE_US;

  float a1[3] = {0}, g1[3] = {0}, a2[3] = {0}, g2[3] = {0};
  float gx, gy, gz;
  bool ok1 = readMPU(imu1.addr, a1[0], a1[1], a1[2], gx, gy, gz);
  if (ok1) { g1[0] = gx - imu1.gBiasX; g1[1] = gy - imu1.gBiasY; g1[2] = gz - imu1.gBiasZ; }
  bool ok2 = readMPU(imu2.addr, a2[0], a2[1], a2[2], gx, gy, gz);
  if (ok2) { g2[0] = gx - imu2.gBiasX; g2[1] = gy - imu2.gBiasY; g2[2] = gz - imu2.gBiasZ; }

  if (++count < 50) return;                  // 50번(0.5초)에 한 번만 출력
  count = 0;

  if (ok1) printImu("IMU 1", a1[0], a1[1], a1[2], g1[0], g1[1], g1[2]);
  else     Serial.println("[IMU 1] Read failed!");
  if (ok2) printImu("IMU 2", a2[0], a2[1], a2[2], g2[0], g2[1], g2[2]);
  else     Serial.println("[IMU 2] Read failed!");
  Serial.println("----------------------------");
}
