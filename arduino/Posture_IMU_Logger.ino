
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

Adafruit_MPU6050 upper;
Adafruit_MPU6050 lower;

// 목표: 50Hz = 20,000마이크로초
const uint32_t INTERVAL_US = 20000;
uint32_t nextSample;

void setup() {
  Serial.begin(115200);

  // XIAO ESP32-S3
  // SDA = GPIO5, SCL = GPIO6
  Wire.begin(5, 6);

  // 센서 2개 초기화
  if (!upper.begin(0x68, &Wire)) {
    Serial.println("Upper IMU Error");
    while (1) delay(100);
  }

  if (!lower.begin(0x69, &Wire)) {
    Serial.println("Lower IMU Error");
    while (1) delay(100);
  }

  upper.setAccelerometerRange(MPU6050_RANGE_2_G);
  lower.setAccelerometerRange(MPU6050_RANGE_2_G);

  upper.setGyroRange(MPU6050_RANGE_250_DEG);
  lower.setGyroRange(MPU6050_RANGE_250_DEG);

  // CSV 헤더
  Serial.println(
    "time_us,T_ax,T_ay,T_az,T_gx,T_gy,T_gz,"
    "L_ax,L_ay,L_az,L_gx,L_gy,L_gz"
  );

  nextSample = micros() + INTERVAL_US;
}

void loop() {
  uint32_t now = micros();

  // 측정할 시간이 아니면 다음 반복으로
  if ((int32_t)(now - nextSample) < 0) {
    return;
  }

  // 다음 측정 예정 시각
  nextSample += INTERVAL_US;

  sensors_event_t a1, g1, t1;
  sensors_event_t a2, g2, t2;

  // 두 센서 데이터 읽기
  bool ok1 = upper.getEvent(&a1, &g1, &t1);
  bool ok2 = lower.getEvent(&a2, &g2, &t2);

  if (!ok1 || !ok2) {
    return;
  }

  // 측정 시작 시각 (마이크로초)
  Serial.print(now);
  Serial.print(",");

  Serial.print(a1.acceleration.x, 4); Serial.print(",");
  Serial.print(a1.acceleration.y, 4); Serial.print(",");
  Serial.print(a1.acceleration.z, 4); Serial.print(",");
  Serial.print(g1.gyro.x, 4); Serial.print(",");
  Serial.print(g1.gyro.y, 4); Serial.print(",");
  Serial.print(g1.gyro.z, 4); Serial.print(",");

  Serial.print(a2.acceleration.x, 4); Serial.print(",");
  Serial.print(a2.acceleration.y, 4); Serial.print(",");
  Serial.print(a2.acceleration.z, 4); Serial.print(",");
  Serial.print(g2.gyro.x, 4); Serial.print(",");
  Serial.print(g2.gyro.y, 4); Serial.print(",");
  Serial.println(g2.gyro.z, 4);

  // 작업 시간이 주기를 초과하면 일정 재설정
  if ((int32_t)(micros() - nextSample) >= 0) {
    nextSample = micros() + INTERVAL_US;
  }
}
