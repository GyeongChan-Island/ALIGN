// Dual_IMU_Test
// 1차 실습(2026-11-08)에서 쓴 코드.
// ESP32-WROOM-32 하나에 MPU6050 두 개를 같은 I2C 버스로 연결하고,
// 라이브러리 없이 레지스터를 직접 읽어 가속도(g)와 자이로(°/s)를 출력한다.
//
// 배선: SDA = GPIO 21, SCL = GPIO 22
//       IMU 1 AD0 -> GND (0x68, 흉추) / IMU 2 AD0 -> 3V3 (0x69, 요추)

#include <Wire.h>

#define MPU1_ADDR 0x68
#define MPU2_ADDR 0x69

// PWR_MGMT_1(0x6B)에 0을 써서 슬립 모드 해제
bool initMPU(uint8_t address) {
  Wire.beginTransmission(address);
  Wire.write(0x6B);
  Wire.write(0x00);
  return Wire.endTransmission() == 0;
}

// 0x3B부터 14바이트: 가속도 XYZ, 온도, 자이로 XYZ
bool readMPU(uint8_t address,
             float &ax, float &ay, float &az,
             float &gx, float &gy, float &gz) {
  Wire.beginTransmission(address);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) {
    return false;
  }
  if (Wire.requestFrom(address, (uint8_t)14) != 14) {
    return false;
  }

  int16_t rawAX = (Wire.read() << 8) | Wire.read();
  int16_t rawAY = (Wire.read() << 8) | Wire.read();
  int16_t rawAZ = (Wire.read() << 8) | Wire.read();
  int16_t temp  = (Wire.read() << 8) | Wire.read();
  int16_t rawGX = (Wire.read() << 8) | Wire.read();
  int16_t rawGY = (Wire.read() << 8) | Wire.read();
  int16_t rawGZ = (Wire.read() << 8) | Wire.read();
  (void)temp;

  // 기본 범위 ±2g, ±250°/s 기준 변환
  ax = rawAX / 16384.0;
  ay = rawAY / 16384.0;
  az = rawAZ / 16384.0;
  gx = rawGX / 131.0;
  gy = rawGY / 131.0;
  gz = rawGZ / 131.0;
  return true;
}

void printIMU(const char *name, uint8_t address) {
  float ax, ay, az, gx, gy, gz;
  if (!readMPU(address, ax, ay, az, gx, gy, gz)) {
    Serial.print(name);
    Serial.println(" Read failed!");
    return;
  }
  Serial.print(name);
  Serial.print(" Accel: ");
  Serial.print(ax); Serial.print(", ");
  Serial.print(ay); Serial.print(", ");
  Serial.print(az);
  Serial.print(" | Gyro: ");
  Serial.print(gx); Serial.print(", ");
  Serial.print(gy); Serial.print(", ");
  Serial.println(gz);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(100000);
  delay(1000);

  Serial.println("Dual MPU6050 Test");
  Serial.println(initMPU(MPU1_ADDR) ? "IMU 1 connected! (0x68)" : "IMU 1 connection FAILED!");
  Serial.println(initMPU(MPU2_ADDR) ? "IMU 2 connected! (0x69)" : "IMU 2 connection FAILED!");
}

void loop() {
  printIMU("[IMU 1]", MPU1_ADDR);
  printIMU("[IMU 2]", MPU2_ADDR);
  Serial.println("----------------------------");
  delay(500);
}
