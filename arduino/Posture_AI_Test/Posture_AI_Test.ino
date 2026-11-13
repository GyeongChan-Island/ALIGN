// Posture_AI_Test
// IMU 2개(Adafruit MPU6050 라이브러리)와 진동 드라이버(DRV2605L)를 초기화하고
// 두 IMU의 X축 가속도를 1초마다 출력하는 테스트 스케치.

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_DRV2605.h>

// 1. 센서 및 드라이버 객체 생성
Adafruit_MPU6050 upper;  // 상부 등 IMU
Adafruit_MPU6050 lower;  // 허리 IMU
Adafruit_DRV2605 motor;  // 진동모터 드라이버

// I2C 핀
// ESP32-WROOM-32 (ESP32 Dev Module): SDA = GPIO21, SCL = GPIO22  <- 현재 사용
// XIAO ESP32-S3로 바꾸면 5, 6으로 변경
#define I2C_SDA 21
#define I2C_SCL 22

bool upperOK = false;
bool lowerOK = false;
bool motorOK = false;

void setup() {
  Serial.begin(115200);
  delay(1000);

  // 2. I2C 설정
  Wire.begin(I2C_SDA, I2C_SCL);

  Serial.println("Posture AI Starting!");

  // 3. 각 장치 초기화
  upperOK = upper.begin(0x68, &Wire);
  lowerOK = lower.begin(0x69, &Wire);
  motorOK = motor.begin(&Wire);

  Serial.println(upperOK ? "Upper IMU OK" : "Upper IMU ERROR");
  Serial.println(lowerOK ? "Lower IMU OK" : "Lower IMU ERROR");
  Serial.println(motorOK ? "Motor driver OK" : "Motor driver ERROR");

  if (motorOK) {
    motor.useERM();
    motor.selectLibrary(1);
    motor.setMode(DRV2605_MODE_INTTRIG);
  }
}

void loop() {
  // 센서가 없으면 측정하지 않음
  if (!upperOK || !lowerOK) {
    delay(1000);
    return;
  }

  sensors_event_t a1, g1, t1;
  sensors_event_t a2, g2, t2;

  // 4. 두 센서의 측정값 읽기
  upper.getEvent(&a1, &g1, &t1);
  lower.getEvent(&a2, &g2, &t2);

  // 5. 측정값 출력
  Serial.print("Upper AX: ");
  Serial.println(a1.acceleration.x);

  Serial.print("Lower AX: ");
  Serial.println(a2.acceleration.x);

  Serial.println("----------------");

  delay(1000);
}
