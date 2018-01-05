import Dependencies._

val monocleVersion = "1.4.0" // 1.5.0-cats-M1 based on cats 1.0.0-MF

lazy val root = (project in file(".")).
  settings(
    inThisBuild(List(
      organization := "de.frosner",
      scalaVersion := "2.12.4",
      version      := "0.1.0-SNAPSHOT"
    )),
    name := "optics-test",
    libraryDependencies ++= List(
      monocleCore,
      monocleMacro,
      scalaTest % Test,
      monocleLaw % Test
    )
  )
