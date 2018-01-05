package example

import monocle.Iso
import org.scalatest._

class IsoSpec extends FlatSpec with Matchers {

  "The Hello object" should "say hello" in {
    val stringListIso = Iso[String, List[Char]](_.toList)(_.mkString(""))
    stringListIso.modify(_.tail)("Hello") should be("ello")
    "Hello".toList.tail.mkString("") should be("ello")
  }
}
