import sbt._

object Dependencies {
  val monocleVersion = "1.4.0" // 1.5.0-cats-M1 based on cats 1.0.0-MF

  lazy val scalaTest = "org.scalatest" %% "scalatest" % "3.0.3"
  lazy val monocleCore = "com.github.julien-truffaut" %%  "monocle-core"  % monocleVersion
  lazy val monocleMacro = "com.github.julien-truffaut" %%  "monocle-macro" % monocleVersion
  lazy val monocleLaw = "com.github.julien-truffaut" %%  "monocle-law"   % monocleVersion
}
