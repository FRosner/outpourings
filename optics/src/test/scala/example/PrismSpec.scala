package example

import monocle.Prism
import monocle.macros.{GenLens, GenPrism}
import org.scalatest._

class PrismSpec extends FlatSpec with Matchers {

  sealed trait Error
  case object NotFound extends Error
  case class InsufficientSecurityLevel(requiredLevel: Int) extends Error


  "The Hello object" should "say hello" in {
    val securityLevel = GenPrism[Error, InsufficientSecurityLevel]
    securityLevel.all(_.requiredLevel > 10)(InsufficientSecurityLevel(15)) should be(true)
    securityLevel.all(_.requiredLevel > 10)(NotFound) should be(true)
  }
}
